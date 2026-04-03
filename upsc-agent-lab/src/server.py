from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()
app = FastAPI()
templates = Jinja2Templates(directory="src/templates")


def get_db():
    return psycopg2.connect(os.getenv("DATABASE_URL"))


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/graph")
async def get_graph_data():
    """Returns Nodes and Edges for the UI"""
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT id, label, type FROM nodes")
    nodes = [{"id": r[0], "label": r[1], "group": r[2]} for r in cur.fetchall()]

    cur.execute("SELECT source_id, target_id FROM edges")
    edges = [{"from": r[0], "to": r[1]} for r in cur.fetchall()]

    conn.close()
    return {"nodes": nodes, "edges": edges}


@app.get("/api/node/{node_id}")
async def get_node_detail(node_id: int):
    """Returns the content for the Right Panel"""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT content_body FROM nodes WHERE id = %s", (node_id,))
    content = cur.fetchone()
    conn.close()
    return {"content": content[0] if content else "No content found."}
