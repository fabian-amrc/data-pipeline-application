# Spark Testing Guide

This directory contains the Spark operator deployment and example Spark jobs used for testing.

## What is included

- `operator/app.yaml` - Argo CD application for the Spark operator chart
- `operator/values.yaml` - Helm values used by the Spark operator application
- `spark-jobs/app.yaml` - Argo CD application for Spark job resources
- `spark-jobs/jobs/spark-pi-sparkapplication.yaml` - Spark Pi sample job for testing

## How to test

1. Make sure the root app-of-apps parent application is available and synced.
2. Verify the Spark operator application is deployed in the `spark` namespace.
   - The operator should create the `SparkApplication` CRD.
   - Check pods with:

```sh
kubectl get pods -n spark
```

3. Sync the Spark jobs application to deploy the Spark Pi sample.
   - You can apply the Spark jobs app directly if needed:

```sh
kubectl apply -f spark/spark-jobs/app.yaml
```

4. Confirm the Spark Pi application is created and running:

```sh
kubectl get sparkapplications -n spark
kubectl get pods -n spark
```

5. Check logs for the Spark driver pod once it is running:

```sh
kubectl logs -n spark -l spark-role=driver
```

6. If you want Spark UI access, expose the driver web UI or deploy a Spark History Server.
   - The current sample is primarily a functional test of the operator.

## Notes

- The sample Spark Pi job uses the `sparkoperator.k8s.io/v1beta2` API.
- If the operator is not ready, the SparkApplication will remain pending until the CRD is available.
- Update the `spark/spark-jobs/jobs/spark-pi-sparkapplication.yaml` values if you need a different Spark image, main class, or resource sizing.
