# core utility imports
import os
from typing import TypedDict, Literal, Annotated, cast
import subprocess
from dotenv import load_dotenv
# langchain imports
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.vectorstores import InMemoryVectorStore
from langgraph.graph import START, END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import interrupt, Command
# pydantic & other imports
from pydantic import BaseModel, Field, SecretStr
from uuid import uuid4

load_dotenv()

model = ChatOpenAI(
    model="inception/mercury-2",
    base_url="https://openrouter.ai/api/v1",
    api_key=SecretStr(os.environ["OPENROUTER_API_KEY"]),
)

embeddings = OpenAIEmbeddings(
    model="openai/text-embedding-3-small",
    base_url="https://openrouter.ai/api/v1",
    api_key=SecretStr(os.environ["OPENROUTER_API_KEY"]),
)

base_system_message = SystemMessage(content=(
    "Give accurate and short answers to the user."
))
# Define the State ──────────────────────────────────────────
# 
# Instead of using the pre-built MessagesState, we define our OWN state.
# This lets us add extra fields beyond just "messages".

class State(TypedDict):
    messages: Annotated[list, add_messages]
    message_intent: str | None
    next_node: str | None

# ── Structured Output for Classification ─────────────────────
#
# We use Pydantic to define the EXACT shape of the classifier's response.
# with_structured_output() forces the LLM to return this shape — no free-text.

class IntentClassifier(BaseModel):
    message_intent: Literal["chat", "rag", "code"] = Field(..., description="Classify whether the user just wants to chat, needs a RAG answer, " \
    "or is asking for code help. Must be one of 'chat', 'rag', or 'code'.")


# ── The Classifier Node ──────────────────────────────────────

def classify_intent(state: State):
    classifier = model.with_structured_output(IntentClassifier)

    response = cast(IntentClassifier, classifier.invoke([
        SystemMessage(content=(
            "Classify the user's message_intent into one of three categories:\n"
            "- 'chat': General greetings and casual conversation\n"
            "- 'rag': Questions that require searching a knowledge base or database, particularly the gaming related questions\n"
            "- 'code': Requests to write, modify, or execute code/files"
        )),
        state["messages"][-1].content,
    ]))

    return {"message_intent": response.message_intent}


# ── The Route Functions for Conditional Edges ───────────────

## --- Route based on the message intent --- ##

def route_by_message_intent(state: State):
    match state["message_intent"]: 
        case "chat":
            return "chat_node"
        case "rag":
            return "rag_node"
        case _:
            return "prepare_coding_prompt"
        
## --- Route after the human approval step of code node --- ##

def route_after_approval(state: State):
    match state.get("next_node"):
        case "edit_denied":
            return END
        case "revise":
            return "prepare_coding_prompt"
        case _:
            return "code_node"


# ── The Three Specialized Nodes (stubs for now) ──────────────

## --- Chat Node --- ##

def chat_node(state: State):
    response = model.invoke([
        base_system_message,
        SystemMessage(content="You are a friendly conversational assistant. Reply warmly."),
        *state["messages"],
    ])
    return {"messages": [response]}

## --- RAG Node with a basic knowledge base --- ##

### -- Knowledge Base --- ###

KNOWLEDGE = [
    "Speedrunning is a popular gaming challenge where players try to complete a game as fast as possible, often using glitches and optimized routes.",
    "Ravenholm is a fictional town in the Half-Life series, known for its eerie atmosphere and the presence of headcrabs and other alien creatures.",
    "The Combine use City 17 as a dystopian stronghold in Half-Life 2, where resistance fighters rely on guerrilla tactics against transhuman forces.",
    "Undertale's Underground is sealed by a magical barrier, and the player's choices to show mercy or violence determine whether the world is healed or destroyed.",
    "W.D. Gaster is a mysterious character in Undertale, with hidden lore suggesting he was the royal scientist before Alphys, and his fragmented appearances hint at a tragic backstory.",
    "Half-Life and Portal share a universe where Aperture Science and Black Mesa experiments overlap, with Portal's secret 'Rat Man dens' and Half-Life's G-Man manipulations hinting at a larger conspiratorial web.",
    "A 'clutch' is pulling off a decisive play under pressure, often turning a losing situation into a victory with one bold move.",
    "A 'kz' run refers to precise movement through deadly obstacle courses, where frame-perfect jumps and bunny hops are standard practice.",
    "Teabagging is a gaming etiquette term for repeatedly crouching over a defeated opponent as a taunt; it often signifies disrespect or playful rivalry.",
    "A 'skill ceiling' describes how much mastery a game allows, measuring how far dedicated players can push their performance."
]

vector_store = InMemoryVectorStore(embedding=embeddings)
vector_store.add_texts(KNOWLEDGE)

### -- RAG Node itself --- ###

def rag_node(state: State):
    query = state["messages"][-1].content
    documents = vector_store.similarity_search(query, k=3)

    context = "\n".join([f"- {doc.page_content}" for doc in documents])

    response = model.invoke([
        base_system_message,
        SystemMessage(content=(
            "You are a knowledge assistant. Answer the user using only the context below. "
            "If the answer is not in it, say you don't know.\n\n"
            f"Context:\n{context}"
        )),
        *state["messages"],
    ])
    return {"messages": [response]}


## --- Code Node with the Prompt Preparation and Accept Edits nodes --- ##

### -- Preparing the prompt for Claude Code based on the conversation context --- ###

def prepare_coding_prompt(state: State):
    user_prompt = state["messages"][-1].content

    conversation_context = "\n".join(
        f"{('User' if isinstance(m, HumanMessage) else 'Assistant')}: {m.content}"
        for m in state["messages"][-6:]
    )

    rewritten_prompt = model.invoke([
        base_system_message,
        SystemMessage(content=(
            "Your task is to turn the latest user prompt into a clear, standalone instruction "
            "that can be sent to Claude Code. Use the conversation context to resolve any "
            "ambiguous references (like 'it', 'that file', 'my name'). "
            "Output only the rewritten prompt, nothing else."
        )),
        HumanMessage(content=f"Conversation context:\n{conversation_context}\n\nLatest prompt:\n{user_prompt}"),
    ])

    return {"messages": [HumanMessage(content=str(rewritten_prompt.content))]}

### -- Human in the loop for approval of the rewritten prompt --- ###

def accept_edits(state: State):
    user_prompt = state["messages"][-1].content
    
    decision = interrupt(f"Handing off this prompt to Claude Code: {user_prompt}, do you approve? (yes/no or type a revised request)")

    decision_text = str(decision).strip().lower()

    if decision_text in ("yes", "y", "approve", "ok", "okay"):
        return {"next_node": None}
    
    if decision_text in ("no", "n", "reject", "deny"):
        return {"messages": [AIMessage(content="Request rejected.")], "next_node": "edit_denied"}

    return {"messages": [HumanMessage(content=decision_text)], "next_node": "revise"}

### -- The Code Node that executes the code using Claude Code --- ###

def code_node(state: State):
    user_prompt = state["messages"][-1].content
    # hard coded workspace for testing
    workspace = os.path.join(os.getcwd(), "workspace")

    result = subprocess.run(
        ["claude", "-p", f"You are only allowed to work in {workspace}, here is what user says: {user_prompt}", "--permission-mode", "acceptEdits"],
        cwd=workspace,
        capture_output=True,
        text=True,
    )

    output = result.stdout.strip() or result.stderr.strip() or "No output from the code execution."

    return {"messages": [AIMessage(content=output)]}


# — Build the Graph ──────────────────────────────────────────

graph = StateGraph(State)

graph.add_node(classify_intent)
graph.add_node(chat_node)
graph.add_node(rag_node)
graph.add_node(code_node)
graph.add_node(accept_edits)
graph.add_node(prepare_coding_prompt)

graph.add_edge(START, "classify_intent")
graph.add_conditional_edges(
    "accept_edits",
    route_after_approval,
    path_map=[END, "prepare_coding_prompt", "code_node"],
)
graph.add_conditional_edges(
    "classify_intent",
    route_by_message_intent,
    path_map=["chat_node", "rag_node", "prepare_coding_prompt"],
)

graph.add_edge("prepare_coding_prompt", "accept_edits")
graph.add_edge("chat_node", END)
graph.add_edge("rag_node", END)
graph.add_edge("code_node", END)

memory = MemorySaver()
app = graph.compile(checkpointer=memory)

# visualize the graph
visualization_output_path = "graph.png"
app.get_graph().draw_mermaid_png(output_file_path=visualization_output_path)

print(f"Graph visualization saved as {visualization_output_path}")


# ── Run it ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    config = RunnableConfig(configurable={"thread_id": str(uuid4())})

    while True:
        msg = input("\nYou: ")
        if msg.lower() in ("quit", "exit", "q"):
            print("bye!")
            break

        result = app.invoke(
            cast(State, {"messages": [HumanMessage(content=msg)]}),
            config,
        )
        print(f"[Intent: {result['message_intent']}]")

        while "__interrupt__" in result:
            interrupt_prompt = result["__interrupt__"][0].value
            interrupt_response = input(f"{interrupt_prompt}\n> ")

            result = app.invoke(
                Command(resume=interrupt_response),
                config,
            )

        print(f"Assistant: {result['messages'][-1].content}")
