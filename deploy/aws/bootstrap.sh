#!/usr/bin/env bash
set -euo pipefail

instance_type=$1
model=$2
ollama_image=ollama/ollama:0.40.17
app_url=http://127.0.0.1:8000

gpu_args=()
parallel=1
if [[ "$instance_type" == g4dn.xlarge ]]; then
  nvidia-smi
  gpu_args=(--gpus all)
fi
if [[ "$instance_type" == m7i-flex.large ]]; then
  parallel=2
fi

docker network create agentmatrix
docker volume create ollama-models
docker pull "$ollama_image"
docker run -d --name ollama --restart unless-stopped \
  --network agentmatrix --log-driver local --volume ollama-models:/root/.ollama \
  --env OLLAMA_NO_CLOUD=1 --env OLLAMA_CONTEXT_LENGTH=8192 \
  --env OLLAMA_NUM_PARALLEL="$parallel" --env OLLAMA_MAX_QUEUE=8 \
  "${gpu_args[@]}" "$ollama_image"

for attempt in {1..30}; do
  if docker exec ollama ollama list; then
    break
  fi
  if [[ "$attempt" -eq 30 ]]; then
    docker logs --tail 50 ollama >&2
    exit 1
  fi
  sleep 2
done
timeout 12m docker exec ollama ollama pull "$model"

docker build --pull --tag agentmatrix:release .
docker run -d --name agentmatrix --restart unless-stopped \
  --network agentmatrix --log-driver local --security-opt no-new-privileges \
  --publish 127.0.0.1:8000:8000 \
  --env AGENTMATRIX_MODE=ollama \
  --env AGENTMATRIX_OLLAMA_BASE_URL=http://ollama:11434 \
  --env AGENTMATRIX_OLLAMA_MODEL="$model" \
  agentmatrix:release

curl --fail --silent --show-error --max-time 8 \
  --retry 12 --retry-all-errors --retry-delay 5 "$app_url/ready"
printf '\n'
smoke_test() {
  curl --fail-with-body --silent --show-error --max-time 200 \
    -H 'Content-Type: application/json' --data "$1" \
    "$app_url/v1/agent/run" | python3 -c '
import json
import sys

response = json.load(sys.stdin)
if (
    response.get("mode") != "ollama"
    or response.get("status") != "completed"
    or not response.get("answer", "").strip()
    or not any(item["id"] == "kb-001" for item in response.get("evidence", []))
):
    sys.exit(f"Unexpected AgentMatrix smoke-test response: {response}")
print("Ollama-backed AgentMatrix smoke test passed. Trace:", response["trace_id"])
'
}
incident_task='{"task":"What changes require approval in the incident response policy?"}'
if [[ "$parallel" -eq 2 ]]; then
  smoke_test "$incident_task" &
  first_request=$!
  smoke_test '{"task":"What investigation can proceed automatically under the incident response policy?"}' &
  second_request=$!
  wait "$first_request"
  wait "$second_request"
else
  smoke_test "$incident_task"
fi
if [[ "$instance_type" == g4dn.xlarge ]]; then
  running_models=$(docker exec ollama ollama ps)
  printf '%s\n' "$running_models"
  grep -q GPU <<< "$running_models"
fi
