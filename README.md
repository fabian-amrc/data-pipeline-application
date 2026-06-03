# Data Pipeline Application

This repository contains an Argo CD app-of-apps scaffold for a Kubernetes data platform.
Applications point at local Kustomize roots. Helm-backed components are rendered with
Kustomize `helmCharts`, using values files committed alongside each app.

## Layout

```text
.
|- app-of-apps/
|  |- app.yaml
|  `- project.yaml
|- argo/
|  |- app.yaml
|  |- kustomization.yaml
|  `- values.yaml
|- spark/
|  |- operator/
|  |  |- app.yaml
|  |  |- kustomization.yaml
|  |  `- values.yaml
|  |- image/
|  |  `- Dockerfile
|  `- spark-applications/
|     |- app.yaml
|     |- kustomization.yaml
|     `- applications/
|- minio/
|  |- operator/
|  |  |- app.yaml
|  |  |- kustomization.yaml
|  |  `- values.yaml
|  `- tenant/
|     |- app.yaml
|     |- kustomization.yaml
|     `- values.yaml
|- unity-catalog/
|  |- app.yaml
|  |- charts/unitycatalog/
|  |- kustomization.yaml
|  |- manifests/
|  `- values.yaml
|- fuseki/
|  |- app.yaml
|  |- kustomization.yaml
|  |- config/
|  `- manifests/
|- semantic-mapper/
|  |- pyproject.toml
|  |- Dockerfile
|  |- src/semantic_mapper/
|  |- resources/
|  `- deploy/base/
`- traefik/
   |- app.yaml
   |- kustomization.yaml
   |- ingressroutes/
   `- values.yaml
```

## Pinned Sources

| Component | Source | Revision |
| --- | --- | --- |
| Argo CD | `https://argoproj.github.io/argo-helm`, chart `argo-cd` | `9.5.15` |
| Spark Operator | `https://kubeflow.github.io/spark-operator`, chart `spark-operator` | `2.5.0` |
| MinIO Operator | `https://operator.min.io`, chart `operator` | `7.1.1` |
| MinIO Tenant | `https://operator.min.io`, chart `tenant` | `7.1.1` |
| Unity Catalog | Vendored from `https://github.com/unitycatalog/unitycatalog.git`, path `helm` | `v0.3.1` |
| Traefik | `https://traefik.github.io/charts`, chart `traefik` | `40.2.0` |
| Apache Jena Fuseki | `stain/jena-fuseki` container image | `5.1.0` |

## Bootstrap

For a local `kind` cluster from inside the devcontainer, run:

```sh
.devcontainer/scripts/setup-kind-cluster.sh
```

The script creates or reuses a `data-pipeline` kind cluster, builds and loads the local Spark image into kind, installs Argo CD, applies the app-of-apps bootstrap manifests, and writes a host-facing kubeconfig to `.devcontainer/kubeconfig`. Use it from your local machine with:

```sh
KUBECONFIG=.devcontainer/kubeconfig k9s
```


Install Argo CD first, then apply the project and root application:

```sh
kubectl apply -f app-of-apps/project.yaml
kubectl apply -f app-of-apps/app.yaml
```

The root application syncs the child `Application` manifests. Child applications point
at local Kustomize roots:

```yaml
source:
  repoURL: https://github.com/fabian-amrc/data-pipeline-application.git
  targetRevision: main
  path: traefik
```

Helm-backed Kustomize roots render charts with `helmCharts`:

```yaml
helmCharts:
  - name: example
    repo: https://example.com/chart-repo
    version: 1.2.3
    releaseName: example
    namespace: example
    valuesFile: values.yaml
```

Argo CD must run Kustomize with Helm enabled. The Argo CD values set
`configs.cm.kustomize.buildOptions: --enable-helm` for this.

## Notes

- Update hostnames, ingress, storage classes, and resource sizing before production use.
- The MinIO tenant values are intentionally small and suitable for a starting point only.
- The Spark smoke-test Python script is stored as a `.py` file and generated into a ConfigMap by Kustomize. Spark applications use the local `data-pipeline-spark:3.5.3` image built from `spark/image`.

- `semantic-mapper/` is the source of truth for ontology/RDL, SHACL shapes, the Semantic Mapper REST API, and metadata projection code. Spark applications register simple mappings through its Python client; the API generates RML, stores mappings centrally, activates the mappings graph in Fuseki, and projects selected metadata into Unity Catalog. `fuseki/` owns the triplestore runtime implementation.

## Local Dashboard Access

The repo deploys Traefik and exposes dashboard routes for:

- `traefik.local` → Traefik dashboard
- `argocd.local` → Argo CD UI
- `minio.local` → MinIO console
- `unity-catalog.local` → Unity catalog UI

If you are running locally, add entries to your `/etc/hosts` file such as:

```text
127.0.0.1 traefik.local argocd.local minio.local unity-catalog.local
```

Then access the dashboards in your browser at the matching hostnames.
