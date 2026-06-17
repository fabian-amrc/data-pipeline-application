import React, { useEffect, useMemo, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import CytoscapeComponent from 'react-cytoscapejs';
import './styles.css';

const SPARQL_ENDPOINT = '/fuseki/semantic/sparql';
const GRAPH_QUERY = `SELECT DISTINCT ?graph WHERE {
  GRAPH ?graph { ?s ?p ?o }
}
ORDER BY ?graph`;

function graphQuery(graph) {
  return `SELECT ?s ?p ?o WHERE {
  GRAPH <${graph}> {
    ?s ?p ?o
  }
}
LIMIT 100`;
}

function label(value) {
  if (!value) return '';
  const trimmed = String(value).replace(/[>#]$/, '');
  const hash = trimmed.lastIndexOf('#');
  const slash = trimmed.lastIndexOf('/');
  const idx = Math.max(hash, slash);
  return idx >= 0 ? trimmed.slice(idx + 1) : trimmed;
}

async function sparql(query) {
  const response = await fetch(SPARQL_ENDPOINT, {
    method: 'POST',
    credentials: 'include',
    headers: {
      Accept: 'application/sparql-results+json',
      'Content-Type': 'application/sparql-query',
    },
    body: query,
  });
  const text = await response.text();
  if (!response.ok) {
    throw new Error(`SPARQL ${response.status}: ${text.slice(0, 500)}`);
  }
  return JSON.parse(text);
}

function bindingsToRows(result) {
  const vars = result?.head?.vars || [];
  const rows = result?.results?.bindings || [];
  return rows.map((row) => Object.fromEntries(vars.map((name) => [name, row[name] || null])));
}

function triplesFromRows(rows) {
  return rows
    .filter((row) => row.s && row.p && row.o)
    .map((row) => ({
      s: row.s.value,
      p: row.p.value,
      o: row.o.value,
      objectType: row.o.type,
    }));
}

function cytoscapeElements(triples) {
  const nodes = new Map();
  const edges = [];
  triples.slice(0, 150).forEach((triple, index) => {
    if (!nodes.has(triple.s)) {
      nodes.set(triple.s, {
        data: { id: triple.s, label: label(triple.s), fullIri: triple.s, type: 'subject' },
        classes: 'subject',
      });
    }
    if (!nodes.has(triple.o)) {
      const type = triple.objectType === 'uri' ? 'resource' : 'literal';
      nodes.set(triple.o, {
        data: { id: triple.o, label: label(triple.o), fullIri: triple.o, type },
        classes: type,
      });
    }
    edges.push({
      data: {
        id: `edge-${index}`,
        source: triple.s,
        target: triple.o,
        label: label(triple.p),
        predicate: triple.p,
      },
    });
  });
  return [...nodes.values(), ...edges];
}

const cytoscapeStylesheet = [
  {
    selector: 'node',
    style: {
      label: 'data(label)',
      'font-size': 10,
      'font-weight': 700,
      color: '#172026',
      'text-wrap': 'wrap',
      'text-max-width': 110,
      'text-valign': 'bottom',
      'text-halign': 'center',
      'text-margin-y': 8,
      width: 34,
      height: 34,
      'border-width': 2,
      'border-color': '#226579',
      'background-color': '#ffffff',
    },
  },
  {
    selector: 'node.subject',
    style: {
      width: 42,
      height: 42,
      'background-color': '#f3b34c',
      'border-color': '#925f09',
    },
  },
  {
    selector: 'node.literal',
    style: {
      shape: 'round-rectangle',
      width: 36,
      height: 24,
      'background-color': '#e8eef2',
      'border-color': '#778891',
    },
  },
  {
    selector: 'edge',
    style: {
      width: 1.5,
      label: 'data(label)',
      'font-size': 9,
      color: '#52626a',
      'curve-style': 'bezier',
      'target-arrow-shape': 'triangle',
      'target-arrow-color': '#8aa0a9',
      'line-color': '#8aa0a9',
      'text-background-color': '#ffffff',
      'text-background-opacity': 0.86,
      'text-background-padding': 2,
    },
  },
  {
    selector: ':selected',
    style: {
      'border-color': '#d14f3f',
      'line-color': '#d14f3f',
      'target-arrow-color': '#d14f3f',
    },
  },
];

const cytoscapeLayout = {
  name: 'cose',
  animate: false,
  fit: true,
  padding: 36,
  nodeRepulsion: 9000,
  idealEdgeLength: 110,
  edgeElasticity: 90,
  gravity: 0.16,
  numIter: 1600,
};

function App() {
  const [graphs, setGraphs] = useState([]);
  const [filter, setFilter] = useState('');
  const [selectedGraph, setSelectedGraph] = useState('');
  const [query, setQuery] = useState('');
  const [result, setResult] = useState(null);
  const [status, setStatus] = useState('Ready');
  const [error, setError] = useState('');
  const [activeView, setActiveView] = useState('visual');

  const rows = useMemo(() => bindingsToRows(result), [result]);
  const triples = useMemo(() => triplesFromRows(rows), [rows]);
  const cyRef = useRef(null);
  const cyElements = useMemo(() => cytoscapeElements(triples), [triples]);
  const filteredGraphs = useMemo(() => graphs.filter((g) => g.toLowerCase().includes(filter.toLowerCase())), [graphs, filter]);

  async function loadGraphs() {
    setStatus('Loading graphs');
    setError('');
    try {
      const data = await sparql(GRAPH_QUERY);
      const nextGraphs = (data.results?.bindings || []).map((row) => row.graph.value);
      setGraphs(nextGraphs);
      if (!selectedGraph && nextGraphs.length) {
        setSelectedGraph(nextGraphs[0]);
        setQuery(graphQuery(nextGraphs[0]));
      }
      setStatus(`${nextGraphs.length} graph${nextGraphs.length === 1 ? '' : 's'} found`);
    } catch (err) {
      setError(err.message);
      setStatus('Graph discovery failed');
    }
  }

  async function runQuery() {
    setStatus('Running query');
    setError('');
    try {
      const data = await sparql(query);
      setResult(data);
      const count = data.results?.bindings?.length || 0;
      setStatus(`${count} row${count === 1 ? '' : 's'} returned`);
    } catch (err) {
      setError(err.message);
      setStatus('Query failed');
    }
  }

  function chooseGraph(graphIri) {
    setSelectedGraph(graphIri);
    setQuery(graphQuery(graphIri));
    setResult(null);
    setStatus(`Selected ${label(graphIri)}`);
  }

  useEffect(() => {
    loadGraphs();
  }, []);

  function fitGraph() {
    const cy = cyRef.current;
    if (cy) {
      cy.layout(cytoscapeLayout).run();
      cy.fit(undefined, 36);
    }
  }

  return (
    <main className="shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brandMark">RG</div>
          <div>
            <h1>RDF Graph Explorer</h1>
            <p>Named graphs in Fuseki</p>
          </div>
        </div>

        <div className="actions">
          <button type="button" onClick={loadGraphs}>Refresh</button>
          <button type="button" onClick={runQuery}>Run</button>
        </div>

        <label htmlFor="graphFilter">Graphs</label>
        <input id="graphFilter" value={filter} onChange={(event) => setFilter(event.target.value)} placeholder="Filter graph IRIs" />

        <div className="graphList">
          {filteredGraphs.map((graphIri) => (
            <button
              key={graphIri}
              type="button"
              className={graphIri === selectedGraph ? 'graphItem active' : 'graphItem'}
              onClick={() => chooseGraph(graphIri)}
              title={graphIri}
            >
              <span>{label(graphIri)}</span>
              <small>{graphIri}</small>
            </button>
          ))}
          {!filteredGraphs.length && <div className="emptySmall">No graphs found</div>}
        </div>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <div className="selected">{selectedGraph || 'No graph selected'}</div>
            <div className={error ? 'status error' : 'status'}>{error || status}</div>
          </div>
          <div className="tabs">
            <button type="button" onClick={fitGraph}>Fit</button>
            {['visual', 'table', 'raw'].map((view) => (
              <button key={view} type="button" className={activeView === view ? 'active' : ''} onClick={() => setActiveView(view)}>
                {view}
              </button>
            ))}
          </div>
        </header>

        <section className="queryPanel">
          <label htmlFor="queryEditor">SPARQL</label>
          <textarea id="queryEditor" value={query} onChange={(event) => setQuery(event.target.value)} spellCheck="false" />
        </section>

        {activeView === 'visual' && (
          <section className="visualPanel">
            {!triples.length && <div className="empty">Run a query returning ?s ?p ?o to visualize triples.</div>}
            {!!triples.length && (
              <CytoscapeComponent
                elements={cyElements}
                stylesheet={cytoscapeStylesheet}
                layout={cytoscapeLayout}
                className="cyGraph"
                cy={(cy) => {
                  cyRef.current = cy;
                  cy.on('tap', 'node, edge', (event) => {
                    const item = event.target;
                    setStatus(item.data('fullIri') || item.data('predicate') || item.data('label'));
                  });
                }}
                wheelSensitivity={0.22}
              />
            )}
          </section>
        )}

        {activeView === 'table' && (
          <section className="tablePanel">
            <table>
              <thead>
                <tr>{(result?.head?.vars || []).map((name) => <th key={name}>{name}</th>)}</tr>
              </thead>
              <tbody>
                {rows.map((row, index) => (
                  <tr key={index}>
                    {(result?.head?.vars || []).map((name) => <td key={name}>{row[name]?.value || ''}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        )}

        {activeView === 'raw' && <pre className="rawPanel">{result ? JSON.stringify(result, null, 2) : ''}</pre>}
      </section>
    </main>
  );
}

createRoot(document.getElementById('root')).render(<App />);
