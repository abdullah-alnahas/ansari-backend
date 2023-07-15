from typing import Any, Optional
from uuid import UUID
import gradio as gr
from rich import print
import re
import random
import time
import asyncio
from asyncio import Queue
from threading import Thread
from queue import SimpleQueue
from langchain.chat_models import ChatOpenAI, PromptLayerChatOpenAI
from langchain.llms import OpenAI
from langchain.callbacks.base import AsyncCallbackHandler, BaseCallbackHandler
from langchain import PromptTemplate, LLMChain
from langchain.prompts.chat import (
    ChatPromptTemplate,
    SystemMessagePromptTemplate,
    AIMessagePromptTemplate,
    HumanMessagePromptTemplate,
)
from langchain.vectorstores.vectara import Vectara
from langchain.schema import (
    AIMessage,
    HumanMessage,
    LLMResult,
    SystemMessage
)
from constants import (
    GREETING, 
    MAX_LENGTH, 
    END, 
    SYSTEM_MESSAGE, 
    CSS, 
    MODEL, 
    STRONG_MODEL, 
    NEWS
)
from kalemat_api import KalematAPI
from quran_search import lookup_quran, determine_quranic, quranic_results
import uuid


with gr.Blocks(title='Ansari', css=CSS) as demo:

    def get_new_id():
        return str(uuid.uuid4())
    
    class MyCBH(BaseCallbackHandler):
        def __init__(self, q):
            self.q = q

        def on_llm_new_token(
            self,
            token,
            *,
            run_id,
            parent_run_id = None,
            **kwargs,
        ) -> None:
            self.q.put(token,my_id)
        
        def on_llm_end(self, response, *, run_id, parent_run_id, **kwargs):
            self.q.put(END, my_id)
        

    my_id = gr.State(get_new_id)
    history = gr.State([['', GREETING]])
    openai_history = gr.State([SystemMessage(content=SYSTEM_MESSAGE), AIMessage(content=GREETING)])
    gr.Markdown(value=NEWS)
    chatbot_ui = gr.Chatbot(value=[[None, GREETING]],elem_id="chatbot")
    msg_ui = gr.Textbox(show_label=False) 


    state_vars = [history, openai_history, my_id]

    def user(user_message, chatbot_ui, history, openai_history, my_id):
        openai_history.append(HumanMessage(content=user_message))
        quranic = determine_quranic(user_message)
        print(f'oai returned {quranic}')
        if quranic: 
            quran_message = quranic_results(user_message)
            print(f'quran message is: {quran_message}')
            openai_history.append(SystemMessage(content=quran_message))
        return gr.update(value=""), history + [[user_message, None]],  history + [[user_message, None]], openai_history, my_id

    def bot(chatbot_ui, history, openai_history, my_id):
        q = SimpleQueue() 
        oai = ChatOpenAI(streaming=True, temperature=0, model_name=STRONG_MODEL,
                    callbacks=[MyCBH(q)], pl_tags=[f'ansari-{my_id}'])
        #print(f'History is {history}')
        history[-1][1] =''
        # Now we have to drop our history
        num_tokens = oai.get_num_tokens_from_messages(openai_history)
        print(f'Num tokens is: {num_tokens}')
        # Loop repeatedly cutting history til it's less
        # Note: There is no need to trim the history. 
        # We just need to trim the openAI history. 
        while num_tokens > MAX_LENGTH: 
            openai_history.pop(0)
            num_tokens = oai.get_num_tokens_from_messages(openai_history)
            print(f'Reduced num_tokens to {num_tokens}')

        thread =  Thread(target = oai.predict_messages, kwargs = {'messages': openai_history})
        thread.start() 
        while True: 
            token = q.get()
            if token == END:
               break
            history[-1][1] += token
            yield history, history, openai_history, my_id
        openai_history.append(AIMessage(content=history[-1][1]))
        #print(f'OpenAI history is: {openai_history}')
        return chatbot_ui, history, openai_history, my_id


    response = msg_ui.submit(user, 
                             [msg_ui, chatbot_ui] + state_vars, 
                             [msg_ui, chatbot_ui] + state_vars, 
                             queue=False).then(
        bot, [chatbot_ui] + state_vars, [chatbot_ui] + state_vars
    )

demo.queue(concurrency_count=8)
demo.launch(favicon_path='./favicon.ico')