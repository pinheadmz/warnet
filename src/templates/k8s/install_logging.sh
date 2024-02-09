#!/bin/bash
set -e

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

helm repo add grafana https://grafana.github.io/helm-charts
helm repo update

helm upgrade --install --namespace warnet-logging --create-namespace --values "${SCRIPT_DIR}/loki/values.yaml" loki grafana/loki
helm upgrade --install --namespace warnet-logging promtail grafana/promtail
helm upgrade --install --namespace warnet-logging loki-grafana grafana/grafana