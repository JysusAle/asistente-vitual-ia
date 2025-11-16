import flet 
from flet import Page, TextField, Dropdown, Column, Text, ElevatedButton, Container, Colors, Row, dropdown
from openai import OpenAI
import requests
from dotenv import load_dotenv
import os
from analisis import identificar_tema
from inferencia import *
from tokenizacion import generar_respuesta

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def funcion():
    return "Hola soy dinoBot, tu asistente virtual"

"""""
def get_ai_reponse(inferencia, prompt):
    try: 
        response = client.chat.completions.create(
            model = "gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": inferencia},
                {"role": "user", "content": prompt}
            ],

            max_tokens=500,
        )
        return response.choices[0].message.content

    except Exception as e:
        return f"Error al generar la respuesta"
    
"""""

def main(page: Page):
    page.title = "DinoBot - Asistente Virtual"
    page.bgcolor = Colors.BLUE_GREY_900
    page.theme_mode = flet.ThemeMode.DARK 
    
    input_box = TextField(
        label="Escribe tu mensaje aquí",
        border_color=Colors.BLUE_200,
        focused_border_color=Colors.BLUE_400,
        text_style=flet.TextStyle(color=Colors.WHITE),
        expand=True
    )

    chat_area = Column(scroll="auto", expand=True)

    def send_message(e):
        kb_musica = "kb/kb_musica.json"
        kb_metro = "kb/kb_metro.json"
        kb_medico = "kb/kb_medico.json"
        kb_general = "kb/kb_general.json"

        user_message = input_box.value
        if not user_message:
            return
        
        chat_area.controls.append(Text(f"Tu: {user_message}", color=Colors.WHITE))

        tema = identificar_tema(user_message)

        if tema == "musica":
            response = generar_respuesta(tema,inferir_recomendacion_musica(user_message, kb_musica),kb_musica)
        if tema == "medicina":
            response = generar_respuesta(tema,inferir_enfermedad(user_message,kb_medico),kb_medico)
        if tema == "tema general": 
            response = generar_respuesta(tema,user_message,kb_general)

        chat_area.controls.append(Text(f"DinoBot: {response}", color=Colors.BLUE_200))
        
        input_box.value = ""
        page.update()

    send_button = ElevatedButton(
        text="Enviar",
        on_click=send_message,
        bgcolor=Colors.BLUE_700,
        color=Colors.WHITE
    )

    chat_container = Container(
        content=chat_area,
        bgcolor=Colors.BLUE_GREY_800,
        padding=10,
        border_radius=10,
        expand=True
    )
    
    input_container = Container(
        content=Row(  
            controls=[
                input_box,
                send_button
            ],
            spacing=10
        )
    )

    main_layout = Column(
        controls=[
            chat_container,
            input_container
        ],
        expand=True,
        spacing=10
    )

    page.add(main_layout)

    page.window.width = 800
    page.window.height = 600
    
    page.update()

if __name__ == "__main__":
    flet.app(target=main)