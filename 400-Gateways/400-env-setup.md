# 1. Starting and Restarting Solace Agent Mesh

Once you have configured your `.env.config` file, use the command below to set up and run Solace Agent Mesh in this codespace.

You can run this command again anytime to restart SAM.

```
cd ./400-Orchestration
source ./400-setup.sh
```

This single command will:

- Create or re-activate the Python virtual environment

- Apply your existing configurations

- Start or restart Solace Agent Mesh

- Print the clickable SAM Web UI link

> Note: the xxx-setup.sh scripts were added to this codelab to simplify setup and configuration in the learning environment. In a real Solace Agent Mesh environment, setup and startup are performed manually rather than through a helper script.
