# Already configured your environment?

## 1. Want to skip doing it again? Run the setup.sh script

```
cd ./300-Agents
source ./300-setup.sh
```

## 2. Opened a new terminal?

Anytime you open a new terminal, you will have to navigate to the sam dir and activate the python virtual environment

```
.venv/bin/activate
sam run
```

## 3. Add Agents from the Catalog

You can add pre-built agents from our plugin catalog by killing the process and running

```
sam plugin catalog
```

a. Select sam_sql_database_tool --> install
b. name it "customer-sql-agent"
c. Click "Install Plugin"
