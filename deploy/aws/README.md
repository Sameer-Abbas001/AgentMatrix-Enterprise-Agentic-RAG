# Run AgentMatrix and Ollama on AWS

CloudFormation runs AgentMatrix and Ollama on one EC2 instance. Both containers restart with the
instance, and the Ollama model cache lives on encrypted EBS. The AWS host downloads and runs
the model. You can close CloudShell or turn off your laptop after deployment.

The API listens on the instance's loopback interface. Access it through IAM-authenticated
AWS Systems Manager Session Manager. Ollama is reachable only on the Docker network.
The existing knowledge base and retrieval logic supply the evidence Ollama uses for synthesis.

## Deploy from AWS CloudShell

Open [AWS CloudShell in Mumbai](https://ap-south-1.console.aws.amazon.com/cloudshell/home?region=ap-south-1)
in an AWS account that can provision CloudFormation, IAM, EC2 and S3 resources and read the
AWS public AMI parameters in Systems Manager. Use a standard CloudShell environment with
internet access. The larger CPU and GPU profiles also use EC2 Auto Scaling.

Upload **AgentMatrix-AWS.zip** using **Actions → Upload file**. If you already have the
updated repository in CloudShell, run the deploy script from the repository instead.

```bash
unzip AgentMatrix-AWS.zip
cd AgentMatrix-Enterprise-Agentic-RAG
bash deploy/aws/deploy.sh ap-south-1 test
```

The `test` profile creates the **agentmatrix-test** stack. It uses one Free Tier-eligible
**m7i-flex.large** instance with 8 GiB RAM, a 40 GiB gp3 root disk and **qwen2.5:1.5b**.
The script checks the instance type and Amazon Linux image for Free Tier eligibility before
uploading the release. Ollama can process two requests concurrently, and deployment performs
a two-request smoke test. Inference runs on CPU, so response times can vary.

The `cpu` and `gpu` profiles create the **agentmatrix** stack with **qwen2.5:7b** and an
80 GiB disk. They use **m7i.xlarge** and **g4dn.xlarge** respectively. GPU mode requires a
sufficient On-Demand G and VT vCPU quota and available capacity. If the first Availability Zone
lacks capacity, retry with `AGENTMATRIX_AZ` set to another standard zone offering the selected
instance type. A failed first-time stack in `ROLLBACK_COMPLETE` must be deleted before retrying.

The deployment uploads the application bundle to a private, regional S3 bucket under your
account. EC2 startup pulls the Ollama image and model, builds the API container, then executes
a real inference request through AgentMatrix. CloudFormation waits up to 30 minutes for this
boot check. The deploy command prints the EC2 instance ID after a successful rollout.

Set `AGENTMATRIX_OLLAMA_MODEL` before deployment to choose another locally runnable Ollama model
tag that fits the selected instance. Running the deploy command again applies changes and
can replace the EC2 instance, briefly interrupting API access and downloading the model again.

AWS meters EC2, EBS, public IPv4 used for outbound connectivity, and S3 storage. The
security group permits no inbound connections. On the AWS Free account plan, eligible usage
uses your credits until the plan expires. The [AWS Pricing Calculator](https://calculator.aws/)
can estimate credit usage for your region and instance type.

## Open the AgentMatrix workspace

**From a browser with access to AWS:** Open the instance in the EC2 console in the deployment
region and select **Connect → Session Manager → Connect**. Run the following from the
instance's browser terminal.

```bash
curl --fail-with-body http://127.0.0.1:8000/ready
curl --fail-with-body http://127.0.0.1:8000/v1/agent/run \
  -H 'Content-Type: application/json' \
  --data '{"task":"What changes require approval in the incident response policy?"}'
```

A successful response shows `"mode":"ollama"`, an answer, and retrieved evidence. The
browser terminal can close while both services continue running.

**To open the research workspace on your device:** Run the port-forwarding command printed
by the deploy script on a device with authenticated AWS CLI and the
[Session Manager plugin](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-install-plugin.html).
Use [the research workspace](http://127.0.0.1:8000/) while the tunnel is open. The address
belongs to the tunnel on your device, and the inference runs on EC2. The workspace links to
[the API docs](http://127.0.0.1:8000/docs).
For two testers, each can open their own tunnel with their own authorized AWS identity.

## Operating the stack

Use the EC2 browser session to inspect startup or runtime logs.

```bash
sudo journalctl -u agentmatrix-bootstrap -b --no-pager
sudo docker logs --tail 100 agentmatrix
sudo docker logs --tail 100 ollama
sudo docker exec ollama ollama ps
```

For a failed stack, review **CloudFormation → Events** in the deployment region. Initial
startup failures can trigger rollback and terminate the instance. If the instance has already
been terminated, inspect CloudFormation events before retrying.

With the `test` profile, use **EC2 → Instances → Instance state → Stop instance** between tests.
Stopping pauses compute and public IPv4 usage. The EBS disk retains the downloaded model and
continues to use storage credits. Starting the same instance restarts both services.

Delete the CloudFormation stack when testing is finished to remove the instance and its EBS
disk. The larger CPU and GPU profiles use an Auto Scaling group that replaces stopped
instances, so delete their stacks to stop compute usage. The private S3 release bucket retains
uploaded bundles. When the bundles are no longer needed, remove them in the S3 console.

[AWS CloudShell guide](https://docs.aws.amazon.com/cloudshell/latest/userguide/getting-started.html) ·
[EC2 Free Tier eligibility](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-free-tier-usage.html) ·
[Session Manager access](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-sessions-start.html) ·
[Ollama model library](https://ollama.com/library)
