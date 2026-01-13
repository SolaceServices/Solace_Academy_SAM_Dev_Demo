# Setting Up Solace Agent Mesh

## 1. Navigate to your course directory

```
cd 100-Environment-Installation
```

## 2. Installing Solace Agent Mesh

1. In the `sam` directory, create a virtual environment

```
cd sam
python3 -m venv .venv
```

2. Activate the virtual environment

```
source .venv/bin/activate
```

3. Install the requirements

```
pip install -r requirements.txt
playwright install
```

> Make sure you have activated your virtual environment before proceeding with the demo. Run `source .venv/bin/activate` if you haven't already done so. Anytime you open a new terminal, you will have to navigate to the `sam` dir and activate the python virtual environment

5. Initialize the solace agent mesh

```
sam init
```

6. Open the configuration Portal in the broswer

```
Would you like to configure your project through a web interface in your browser? [Y/n]: y
```

7. In the GUI, select `Advanced Setup` and configure the relevant fields:

- Project Namespace: `Solace-Academy-SAM-Demo`
- Broker Type: `Existing Solace Pub/Sub+ broker`
- Broker URL: `ws://localhost:8008`
- VPN Name: `default`
- Username: `admin`
- Password: `admin`
- LLM Provider: `Your LLM Provider`
- LLM Endpoint URL: `Your LLM Endpoint URL`
- LLM API Key: `Your LLM API Key`
- LLM Model Name: `Your LLM Model Name`

- Session Secret Key: `Create a strong session key`

![VSCode](../assets/Agent%20Mesh%20Init%20GUI.png)

8. After initializing sam, you should now see a

```
.
├── configs
│ ├── agents
│ │ └── main_orchestrator.yaml
│ ├── gateways
│ │ └── webui.yaml
│ ├── logging_config.yaml
│ └── shared_config.yaml
├── requirements.txt
└── src
└── .env
└── requirements.txt
└── sam.log
```

9. Run Solace Agent Mesh

```
sam run
```
