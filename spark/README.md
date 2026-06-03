# Spark Testing Guide

This directory contains the Spark operator deployment and example Spark applications used for testing.

## What is included

- `operator/app.yaml` - Argo CD application for the Spark operator chart
- `operator/values.yaml` - Helm values used by the Spark operator application
- `image/Dockerfile` - Local Spark image with shared Delta, Unity Catalog, Kafka, CA certificate setup, and a stable `spark` runtime user
- `image/conf/spark-defaults.conf` - Shared Spark defaults baked into the local image, including Delta, Unity Catalog, and MinIO S3A defaults; per-application `spec.sparkConf` values override these at submit time
- `spark-applications/app.yaml` - Argo CD application for SparkApplication resources
- `spark-applications/applications/spark-pi/spark-pi-sparkapplication.yaml` - Spark Pi sample application for testing
- `spark-applications/applications/delta-test/delta-test-sparkapplication.yaml` - Delta Lake and MinIO S3A write/read test
- `spark-applications/applications/semantic-test/semantic-test-sparkapplication.yaml` - Writes `unity.default.example_dataset`, registers its mapping through Semantic Mapper, and verifies semantic UC metadata

## How to test

1. Make sure the root app-of-apps parent application is available and synced.
2. Verify the Spark operator application is deployed in the `spark-operator` namespace.
   - The operator should create the `SparkApplication` CRD.
   - Check pods with:

```sh
kubectl get pods -n spark-operator
```

3. Sync the Spark applications application to deploy the Spark Pi sample.
   - You can apply the Spark applications app directly if needed:

```sh
kubectl apply -f spark/spark-applications/app.yaml
```

4. Confirm the Spark Pi application is created and running:

```sh
kubectl get sparkapplications -n spark-jobs
kubectl get pods -n spark-jobs
```

5. Check logs for the Spark driver pod once it is running:

```sh
kubectl logs -n spark-jobs -l spark-role=driver
```

6. The Delta test writes a small table to `s3a://delta/delta-test`, reads it back, and prints the resulting rows. The Spark image provides the default in-cluster MinIO S3A configuration, and applications read credentials from the `myminio-env-configuration` secret mounted at `/var/run/minio-tenant/config.env`. Override `OUTPUT_PATH` in `spark/spark-applications/applications/delta-test/delta-test-sparkapplication.yaml`, or override `spark.hadoop.fs.s3a.endpoint` in `spec.sparkConf`, if your tenant uses different values.

7. If you want Spark UI access, expose the driver web UI or deploy a Spark History Server.
   - The current sample is primarily a functional test of the operator.

## Notes

- The sample Spark Pi job uses the `sparkoperator.k8s.io/v1beta2` API.
- If the operator is not ready, the SparkApplication will remain pending until the CRD is available.
- Update `spark/image/Dockerfile` for shared Spark dependencies or runtime image setup, `spark/image/conf/spark-defaults.conf` for image-level Spark defaults, or the individual SparkApplication manifests for per-job image, `spec.sparkConf`, main class, and resource sizing changes.

## Shared Spark application Python library

Spark application helper code that is shared across jobs lives in `spark/spark-applications/lib`. Kustomize includes those files in each application ConfigMap that needs them, so jobs can import the helpers from `/app` without baking application code into `data-pipeline-spark:3.5.3`.

`lib/minio_s3.py` centralizes MinIO credential resolution, `s3a://` bucket parsing, and standard-library S3 bucket creation. It defaults to the standard in-cluster MinIO endpoint, region, and mounted tenant config path. Keep app-specific defaults and Spark logic in each application directory, and put reusable runtime helpers in `lib` when more than one SparkApplication needs them.

## Declaring Semantics From Spark Applications

Spark applications can describe the datasets they write with the `semantic_mapper` Python client. The client defaults to the in-cluster Semantic Mapper API, `manufacturing-rdl` ontology, and `spark-delta` profile, so application code can usually call `SemanticMapper()` with no configuration.

The semantic test keeps its declaration next to the Spark code in `spark/spark-applications/applications/semantic-test/dataset_semantics.py`. The app writes Delta data, calls `register_and_project()`, and the Semantic Mapper API handles RML generation, validation, mappings-graph activation, and Unity Catalog projection.

## Spark configuration precedence

Spark reads `spark-defaults.conf` as defaults only. The local Spark image merges those defaults with the Spark operator generated properties file at container startup. Values set on a `SparkApplication` under `spec.sparkConf` remain in the generated properties file and override matching image defaults. The image entrypoint reads `/var/run/minio-tenant/config.env` by default, or `MINIO_CONFIG_ENV_FILE` when set, and exports AWS credentials so the shared S3A environment-variable credential provider works for drivers and executors.

## Local Spark image

The kind bootstrap script builds `data-pipeline-spark:3.5.3` using `spark/image/Dockerfile` from the repository root and loads it into the `data-pipeline` kind cluster. The root build context lets the image package the Semantic Mapper Python client from `semantic-mapper/client` for Spark `pyFiles` usage. To add a local MinIO CA certificate, place it at `spark/image/certs/minikubeCA.crt` before running the bootstrap script.

You can build and load the image manually with:

```sh
docker build -t data-pipeline-spark:3.5.3 -f spark/image/Dockerfile .
kind load docker-image data-pipeline-spark:3.5.3 --name data-pipeline
```
