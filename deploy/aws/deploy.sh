#!/usr/bin/env bash
set -euo pipefail

region=${1:-${AWS_REGION:-${AWS_DEFAULT_REGION:-ap-south-1}}}
compute=${2:-test}
case "$compute" in
  test)
    instance_type=m7i-flex.large
    ami_parameter=/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64
    stack=${AGENTMATRIX_STACK:-agentmatrix-test}
    model=${AGENTMATRIX_OLLAMA_MODEL:-qwen2.5:1.5b}
    ;;
  cpu|gpu)
    instance_type=m7i.xlarge
    ami_base=/aws/service/ecs/optimized-ami/amazon-linux-2023
    if [[ "$compute" == gpu ]]; then
      instance_type=g4dn.xlarge
      ami_base="$ami_base/gpu"
    fi
    ami_parameter="$ami_base/recommended/image_id"
    stack=${AGENTMATRIX_STACK:-agentmatrix}
    model=${AGENTMATRIX_OLLAMA_MODEL:-qwen2.5:7b}
    ;;
  *) echo "Unknown compute option: $compute. Use test, cpu or gpu." >&2; exit 2 ;;
esac
if [[ $# -gt 2 || ! "$region" =~ ^[a-z]{2}(-[a-z]+)+-[1-9][0-9]*$ ||
      ! "$stack" =~ ^[a-zA-Z][a-zA-Z0-9-]{0,79}$ ||
      ! "$model" =~ ^[a-zA-Z0-9._/:-]{1,128}$ ]]; then
  echo 'Usage: bash deploy/aws/deploy.sh [aws-region] [test|cpu|gpu]' >&2
  exit 2
fi
export AWS_DEFAULT_REGION="$region" AWS_REGION="$region" AWS_PAGER=''

cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.."
account=$(aws sts get-caller-identity --query Account --output text)
bucket="agentmatrix-releases-$account-$region"
zone=${AGENTMATRIX_AZ:-}
if [[ -z "$zone" ]]; then
  zone=$(aws ec2 describe-instance-type-offerings \
    --location-type availability-zone \
    --filters "Name=instance-type,Values=$instance_type" \
    --query 'sort(InstanceTypeOfferings[].Location)[0]' --output text)
fi
if [[ ! "$zone" =~ ^"$region"[a-z]$ ]]; then
  echo "Choose a standard Availability Zone in $region that offers $instance_type." >&2
  exit 1
fi
image=$(aws ssm get-parameter --name "$ami_parameter" \
  --query Parameter.Value --output text)
image_filters=()
if [[ "$compute" == test ]]; then
  eligible_type=$(aws ec2 describe-instance-types --instance-types "$instance_type" \
    --query 'InstanceTypes[0].FreeTierEligible' --output text)
  if [[ "${eligible_type,,}" != true ]]; then
    echo "$instance_type is not marked as Free Tier eligible in this AWS Region." >&2
    exit 1
  fi
  image_filters=(--filters Name=free-tier-eligible,Values=true)
fi
root_device=$(aws ec2 describe-images --image-ids "$image" "${image_filters[@]}" \
  --query 'Images[0].RootDeviceName' --output text)
if [[ ! "$image" =~ ^ami-[a-f0-9]+$ || ! "$root_device" =~ ^/dev/[a-z0-9]+$ ]]; then
  echo "Could not resolve an eligible Amazon Linux 2023 AMI for $compute in $region." >&2
  exit 1
fi

release=$(mktemp)
trap 'rm -f -- "$release"' EXIT
tar -czf "$release" --sort=name --mtime=@0 --owner=0 --group=0 --numeric-owner \
  --exclude=__pycache__ --exclude='*.pyc' \
  .dockerignore Dockerfile LICENSE README.md pyproject.toml src deploy/aws/bootstrap.sh
read -r sha _ < <(sha256sum "$release")

if ! aws s3api head-bucket --bucket "$bucket" --expected-bucket-owner "$account" \
    >/dev/null 2>&1; then
  location=()
  if [[ "$region" != us-east-1 ]]; then
    location=(--create-bucket-configuration "LocationConstraint=$region")
  fi
  aws s3api create-bucket --bucket "$bucket" "${location[@]}" >/dev/null
fi
aws s3api put-public-access-block --bucket "$bucket" --expected-bucket-owner "$account" \
  --public-access-block-configuration \
  'BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true'
aws s3api put-object --bucket "$bucket" --expected-bucket-owner "$account" \
  --key "agentmatrix/$stack/$sha.tar.gz" --body "$release" \
  --server-side-encryption AES256 >/dev/null

printf 'Deploying %s in %s on %s with model %s.\n' "$stack" "$zone" "$instance_type" "$model"
if ! aws cloudformation deploy --stack-name "$stack" --template-file deploy/aws/stack.yaml \
  --capabilities CAPABILITY_IAM --no-fail-on-empty-changeset \
  --parameter-overrides "AvailabilityZone=$zone" "InstanceType=$instance_type" \
  "ImageId=$image" "RootDevice=$root_device" "ArtifactBucket=$bucket" \
  "ArtifactSha256=$sha" "OllamaModel=$model"; then
  aws cloudformation describe-stack-events --stack-name "$stack" \
    --query 'StackEvents[:12].[LogicalResourceId,ResourceStatus,ResourceStatusReason]' \
    --output table >&2 || true
  exit 1
fi

if [[ "$compute" == test ]]; then
  instance=$(aws cloudformation describe-stacks --stack-name "$stack" \
    --query "Stacks[0].Outputs[?OutputKey=='TestInstanceId'].OutputValue | [0]" --output text)
else
  group=$(aws cloudformation describe-stacks --stack-name "$stack" \
    --query "Stacks[0].Outputs[?OutputKey=='AutoScalingGroupName'].OutputValue | [0]" --output text)
  instance=$(aws autoscaling describe-auto-scaling-groups --auto-scaling-group-names "$group" \
    --query "AutoScalingGroups[0].Instances[?LifecycleState=='InService'].InstanceId | [0]" \
    --output text)
fi
if [[ ! "$instance" =~ ^i-[a-f0-9]+$ ]]; then
  echo "Could not find the EC2 instance for the CloudFormation stack." >&2
  exit 1
fi
printf 'EC2 instance: %s (%s)\n' "$instance" "$region"
printf 'Open a private tunnel from a machine with the AWS CLI and Session Manager plugin:\n'
printf "aws ssm start-session --region %s --target %s --document-name AWS-StartPortForwardingSession --parameters 'portNumber=8000,localPortNumber=8000'\n" "$region" "$instance"
printf 'AgentMatrix workspace during the session: http://127.0.0.1:8000/\n'
