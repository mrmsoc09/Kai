import os, yaml
BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
DAG_DIR = os.path.join(BASE, "workflows", "dags")

def load_dag(name: str):
    path = os.path.join(DAG_DIR, f"{name}.yaml")
    with open(path, "r") as f:
        return yaml.safe_load(f)

def plan(name: str, context=None):
    dag = load_dag(name)
    nodes = dag.get("nodes", [])
    return {"name": name, "nodes": [n["id"] for n in nodes], "actions": [n["action"] for n in nodes]}
