from langchain import hub
from langchain_community.agent_toolkits.sql.toolkit import SQLDatabaseToolkit
from langchain_community.utilities import SQLDatabase
from langgraph.prebuilt import create_react_agent
from sqlalchemy.engine import Engine

from relatorios_service.llm import create_chat_model


class SqlAssistant:
    def __init__(
        self,
        engine: Engine,
        allowed_tables: list[str],
    ) -> None:
        database = SQLDatabase(
            engine,
            include_tables=allowed_tables,
            sample_rows_in_table_info=2,
        )

        model = create_chat_model()

        toolkit = SQLDatabaseToolkit(
            db=database,
            llm=model,
        )

        prompt_template = hub.pull(
            "langchain-ai/sql-agent-system-prompt"
        )

        system_message = prompt_template.format(
            dialect=database.dialect,
            top_k=10,
        )

        self.agent = create_react_agent(
            model,
            toolkit.get_tools(),
            state_modifier=system_message,
        )

    def ask(self, question: str) -> str:
        result = self.agent.invoke(
            {
                "messages": [
                    ("user", question),
                ]
            }
        )

        return result["messages"][-1].content
