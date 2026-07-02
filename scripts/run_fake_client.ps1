param(
    [string]$Mode = "normal",
    [string]$NodeId = "node-01"
)

python tests/fake_client.py --node-id $NodeId --mode $Mode

