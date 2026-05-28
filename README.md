# Data Pipeline Application

This repository contains an Argo CD app-of-apps scaffold for a Kubernetes data platform.
Each child application pulls its upstream Helm chart from the project-owned chart source
and pulls environment values from this repository using Argo CD multiple sources.

## Layout

```text
.
|- app-of-apps/
|  |- app.yaml
|  `- project.yaml
|- argo/
|  |- app.yaml
|  `- values.yaml
|- spark/
|  `- operator/
|     |- app.yaml
|     `- values.yaml
|- spark-jobs/
|- minio/
|  |- operator/
|  |  |- app.yaml
|  |  `- values.yaml
|  `- tenant/
|     |- app.yaml
|     `- values.yaml
|- unity-catalog/
|  |- app.yaml
|  `- values.yaml
`- traefik/
   |- app.yaml
   `- values.yaml
```

## Pinned Sources

| Component | Source | Revision |
| --- | --- | --- |
| Argo CD | `https://argoproj.github.io/argo-helm`, chart `argo-cd` | `9.5.15` |
| Spark Operator | `https://kubeflow.github.io/spark-operator`, chart `spark-operator` | `2.5.0` |
| MinIO Operator | `https://github.com/minio/operator.git`, path `helm/operator` | `v7.1.1` |
| MinIO Tenant | `https://github.com/minio/operator.git`, path `helm/tenant` | `v7.1.1` |
| Unity Catalog | `https://github.com/unitycatalog/unitycatalog.git`, path `helm` | `v0.3.1` |
| Traefik | `https://traefik.github.io/charts`, chart `traefik` | `40.2.0` |

## Bootstrap

For a local `kind` cluster from inside the devcontainer, run:

```sh
.devcontainer/scripts/setup-kind-cluster.sh
```

The script creates or reuses a `data-pipeline` kind cluster, installs Argo CD, and applies the app-of-apps bootstrap manifests.


Install Argo CD first, then apply the project and root application:

```sh
kubectl apply -f app-of-apps/project.yaml
kubectl apply -f app-of-apps/app.yaml
```

The root application syncs the child `Application` manifests. Child applications use
Argo CD's multi-source Helm values pattern:

```yaml
sources:
  - repoURL: https://example.com/chart-repo
    chart: example
    targetRevision: 1.2.3
    helm:
      valueFiles:
        - $values/path/to/values.yaml
  - repoURL: https://github.com/fabian-amrc/data-pipeline-application.git
    targetRevision: main
    ref: values
```

## Notes

- Update hostnames, ingress, storage classes, and resource sizing before production use.
- The MinIO tenant values are intentionally small and suitable for a starting point only.
- The `spark-jobs` directory is reserved for SparkApplication manifests or future Argo applications.

## Local Dashboard Access

The repo deploys Traefik and exposes dashboard routes for:

- `traefik.local` → Traefik dashboard
- `argocd.local` → Argo CD UI
- `minio.local` → MinIO console

If you are running locally, add entries to your `/etc/hosts` file such as:

```text
127.0.0.1 traefik.local argocd.local minio.local
```

Then access the dashboards in your browser at the matching hostnames.
