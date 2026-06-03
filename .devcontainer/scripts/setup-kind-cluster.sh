#!/usr/bin/env bash
set -euo pipefail

CLUSTER_NAME="${CLUSTER_NAME:-data-pipeline}"
ARGO_NAMESPACE="${ARGO_NAMESPACE:-argocd}"
KIND_NODE_IMAGE="${KIND_NODE_IMAGE:-kindest/node:v1.34.3@sha256:08497ee19eace7b4b5348db5c6a1591d7752b164530a36f855cb0f2bdcbadd48}"
KIND_POD_SUBNET="${KIND_POD_SUBNET:-10.244.0.0/16}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
HOST_KUBECONFIG="${HOST_KUBECONFIG:-${REPO_ROOT}/.devcontainer/kubeconfig}"
SPARK_IMAGE="${SPARK_IMAGE:-data-pipeline-spark:3.5.3}"
SPARK_IMAGE_CONTEXT="${SPARK_IMAGE_CONTEXT:-${REPO_ROOT}}"
SPARK_IMAGE_BUILD="${SPARK_IMAGE_BUILD:-true}"
SEMANTIC_MAPPER_IMAGE="${SEMANTIC_MAPPER_IMAGE:-data-pipeline-semantic-mapper:0.1.0}"
SEMANTIC_MAPPER_IMAGE_CONTEXT="${SEMANTIC_MAPPER_IMAGE_CONTEXT:-${REPO_ROOT}/semantic-mapper}"
SEMANTIC_MAPPER_IMAGE_BUILD="${SEMANTIC_MAPPER_IMAGE_BUILD:-true}"

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

connect_to_kind_network() {
  local container_name
  container_name="$(hostname)"

  if ! docker inspect "${container_name}" >/dev/null 2>&1; then
    return 0
  fi

  if ! docker network inspect kind >/dev/null 2>&1; then
    return 0
  fi

  if docker inspect "${container_name}" --format '{{json .NetworkSettings.Networks}}' | grep -q '"kind"'; then
    return 0
  fi

  echo "Connecting devcontainer to Docker network: kind"
  docker network connect kind "${container_name}" >/dev/null 2>&1 || true
}

export_internal_kubeconfig() {
  connect_to_kind_network
  kind export kubeconfig --name "${CLUSTER_NAME}" --internal >/dev/null
  kubectl config use-context "kind-${CLUSTER_NAME}" >/dev/null
}

export_host_kubeconfig() {
  echo "Writing host kubeconfig: ${HOST_KUBECONFIG}"
  mkdir -p "$(dirname "${HOST_KUBECONFIG}")"
  kind export kubeconfig --name "${CLUSTER_NAME}" --kubeconfig "${HOST_KUBECONFIG}" >/dev/null
  chmod 600 "${HOST_KUBECONFIG}"
}

build_and_load_spark_image() {
  if [ "${SPARK_IMAGE_BUILD}" != "true" ]; then
    echo "Skipping Spark image build because SPARK_IMAGE_BUILD=${SPARK_IMAGE_BUILD}"
    return 0
  fi

  echo "Building Spark image: ${SPARK_IMAGE}"
  docker build -t "${SPARK_IMAGE}" -f "${REPO_ROOT}/spark/image/Dockerfile" "${SPARK_IMAGE_CONTEXT}"

  echo "Loading Spark image into kind cluster: ${CLUSTER_NAME}"
  kind load docker-image "${SPARK_IMAGE}" --name "${CLUSTER_NAME}"
}

build_and_load_semantic_mapper_image() {
  if [ "${SEMANTIC_MAPPER_IMAGE_BUILD}" != "true" ]; then
    echo "Skipping Semantic Mapper image build because SEMANTIC_MAPPER_IMAGE_BUILD=${SEMANTIC_MAPPER_IMAGE_BUILD}"
    return 0
  fi

  echo "Building Semantic Mapper image: ${SEMANTIC_MAPPER_IMAGE}"
  docker build -t "${SEMANTIC_MAPPER_IMAGE}" "${SEMANTIC_MAPPER_IMAGE_CONTEXT}"

  echo "Loading Semantic Mapper image into kind cluster: ${CLUSTER_NAME}"
  kind load docker-image "${SEMANTIC_MAPPER_IMAGE}" --name "${CLUSTER_NAME}"
}

wait_for_control_plane() {
  local node_name
  node_name="${CLUSTER_NAME}-control-plane"

  echo "Waiting for delayed control plane"
  for _ in {1..60}; do
    if docker exec "${node_name}" test -f /etc/kubernetes/admin.conf >/dev/null 2>&1 && \
      docker exec "${node_name}" kubectl --kubeconfig=/etc/kubernetes/admin.conf get --raw=/readyz >/dev/null 2>&1 && \
      docker exec "${node_name}" kubectl --kubeconfig=/etc/kubernetes/admin.conf get namespace default >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done

  echo "Timed out waiting for ${node_name} to become ready." >&2
  return 1
}

ensure_existing_kind_cluster() {
  local node_name
  node_name="${CLUSTER_NAME}-control-plane"

  if docker ps --format '{{.Names}}' | grep -qx "${node_name}"; then
    wait_for_control_plane
    return 0
  fi

  if docker ps -a --format '{{.Names}}' | grep -qx "${node_name}"; then
    echo "Starting stopped kind control plane: ${node_name}"
    docker start "${node_name}" >/dev/null
    wait_for_control_plane
    return 0
  fi

  echo "kind reports cluster ${CLUSTER_NAME}, but ${node_name} does not exist." >&2
  echo "Delete the stale cluster with: kind delete cluster --name ${CLUSTER_NAME}" >&2
  return 1
}

recover_kind_create() {
  local node_name
  node_name="${CLUSTER_NAME}-control-plane"

  if ! docker ps --format '{{.Names}}' | grep -qx "${node_name}"; then
    return 1
  fi

  wait_for_control_plane

  echo "Completing kind post-create steps"
  docker exec --privileged "${node_name}" kubectl --kubeconfig=/etc/kubernetes/admin.conf \
    taint nodes --all node-role.kubernetes.io/control-plane- >/dev/null 2>&1 || true
  docker exec --privileged "${node_name}" sh -c \
    "sed 's|{{ .PodSubnet }}|\"${KIND_POD_SUBNET}\"|g' /kind/manifests/default-cni.yaml > /tmp/default-cni.yaml"
  docker exec --privileged "${node_name}" kubectl --kubeconfig=/etc/kubernetes/admin.conf \
    apply --validate=false -f /tmp/default-cni.yaml >/dev/null
  docker exec --privileged "${node_name}" kubectl --kubeconfig=/etc/kubernetes/admin.conf \
    apply --validate=false -f /kind/manifests/default-storage.yaml >/dev/null
}

require_command docker
require_command kind
require_command kubectl
require_command kustomize

if ! docker info >/dev/null 2>&1; then
  echo "Docker is not available. Start Docker on the host and make sure the devcontainer has Docker access." >&2
  exit 1
fi

if kind get clusters | grep -qx "${CLUSTER_NAME}"; then
  echo "Using existing kind cluster: ${CLUSTER_NAME}"
  ensure_existing_kind_cluster
  export_internal_kubeconfig
else
  echo "Creating kind cluster: ${CLUSTER_NAME}"
  KIND_CONFIG="$(mktemp)"
  trap 'rm -f "${KIND_CONFIG}"' EXIT

  cat > "${KIND_CONFIG}" <<KIND_CONFIG_EOF
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
  - role: control-plane
    image: ${KIND_NODE_IMAGE}
    extraPortMappings:
      - containerPort: 80
        hostPort: 80
        protocol: TCP
      - containerPort: 443
        hostPort: 443
        protocol: TCP
KIND_CONFIG_EOF

  if ! KIND_CREATE_OUTPUT="$(kind create cluster --name "${CLUSTER_NAME}" --config "${KIND_CONFIG}" --retain 2>&1)"; then
    echo "${KIND_CREATE_OUTPUT}"
    if grep -Eq 'admin\.conf|connection refused' <<<"${KIND_CREATE_OUTPUT}"; then
      recover_kind_create
    else
      exit 1
    fi
  fi

  export_internal_kubeconfig
fi

export_host_kubeconfig
build_and_load_spark_image
build_and_load_semantic_mapper_image

echo "Ensuring namespace exists: ${ARGO_NAMESPACE}"
kubectl create namespace "${ARGO_NAMESPACE}" --dry-run=client -o yaml | kubectl apply -f -

echo "Installing Argo CD with Kustomize Helm"
kustomize build --enable-helm "${REPO_ROOT}/argo" | kubectl apply --server-side --force-conflicts -f -

echo "Waiting for Argo CD deployments"
kubectl wait --for=condition=Available deployment --all -n "${ARGO_NAMESPACE}" --timeout=300s

echo "Applying app-of-apps bootstrap manifests"
kubectl apply -f "${REPO_ROOT}/app-of-apps/project.yaml"
kubectl apply -f "${REPO_ROOT}/app-of-apps/app.yaml"

echo "Waiting for root Argo CD application to be created"
kubectl wait --for=jsonpath='{.metadata.name}'=data-pipeline-apps application/data-pipeline-apps -n "${ARGO_NAMESPACE}" --timeout=120s

echo "Cluster setup complete."
echo "Context: kind-${CLUSTER_NAME}"
echo "Host kubeconfig: ${HOST_KUBECONFIG}"
echo "Spark image: ${SPARK_IMAGE}"
echo "Semantic Mapper image: ${SEMANTIC_MAPPER_IMAGE}"
echo "Local k9s: KUBECONFIG=${HOST_KUBECONFIG} k9s"
echo "Argo CD namespace: ${ARGO_NAMESPACE}"
echo "Initial admin password: kubectl -n ${ARGO_NAMESPACE} get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d && echo"
echo "Argo CD UI port-forward: kubectl -n ${ARGO_NAMESPACE} port-forward svc/argo-cd-argocd-server 8080:80"
