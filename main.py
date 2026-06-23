import os
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from langgraph.graph import START, END, MessagesState, StateGraph
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from pydantic import SecretStr
from uuid import uuid4

load_dotenv()

llm = ChatOpenAI( 
    model="inception/mercury-2",
    base_url="https://openrouter.ai/api/v1",
    api_key=SecretStr(os.environ["OPENROUTER_API_KEY"]),
)


# A node is just a function that takes state and returns updated state
def prompt_llm(state: MessagesState):
    response = llm.invoke(state["messages"])
    return {"messages": [response]}


# Build the graph
graph = StateGraph(MessagesState)
graph.add_node(prompt_llm)
graph.add_edge(START, "prompt_llm")
graph.add_edge("prompt_llm", END)

memory = MemorySaver()
app = graph.compile(checkpointer=memory)

if __name__ == "__main__":
    config = RunnableConfig(configurable={"thread_id": str(uuid4())})

    # First message in thread "1"
    result = app.invoke(
        {"messages": [HumanMessage(content="Hi, my name is Ufuk.")]},
        config,
    )
    print(result["messages"][-1].content)

    # Second message in same thread — the LLM should remember the name
    result = app.invoke(
        {"messages": [HumanMessage(content="What is my name?")]},
        config,
    )
    print(result["messages"][-1].content)
