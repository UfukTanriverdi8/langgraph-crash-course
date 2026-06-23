import os
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from langgraph.graph import START, END, MessagesState, StateGraph
from langchain_core.messages import HumanMessage
from pydantic import SecretStr

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

app = graph.compile()

if __name__ == "__main__":
    result = app.invoke({"messages": [HumanMessage(content="What is LangGraph in one sentence?")]})
    last_message = result["messages"][-1]
    print(last_message.content)
