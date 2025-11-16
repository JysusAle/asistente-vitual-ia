import spacy
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
import json
import random

nlp = spacy.load("es_core_news_md")

def limpiar_texto(texto):
    tokens = word_tokenize(texto.lower(), language='spanish')
    stop_words = set(stopwords.words('spanish'))
    tokens = [t for t in tokens if t.isalpha() and t not in stop_words]
    return " ".join(tokens)

def similitud_semantica(prompt, texto):
    prompt_clean = limpiar_texto(prompt)
    texto_clean = limpiar_texto(texto)
    
    doc1 = nlp(prompt_clean)
    doc2 = nlp(texto_clean)
    
    similitud = doc1.similarity(doc2)

    print(f"\nSimilitud con {texto} con un {similitud}...")

    return round(similitud * 100, 2)


def probabilidad_tema(prompt, resultado):

    prompt_tokens = limpiar_texto(prompt)
    prompt_doc = nlp(" ".join(prompt_tokens))
    
    contador = 0
    for item in resultado:
        item_doc = nlp(item.lower())
        
        similitud = prompt_doc.similarity(item_doc)
        
        if item.lower() in prompt_tokens or similitud > 0.8:
            print(f"\nAnalisis - Reconociendo: {item.lower()} con un {similitud}\n")
            contador += 1
    
    probabilidad_total = contador / len(resultado)
    return round(probabilidad_total * 100, 2)

def generar_respuesta(tema,inferencias,kb):

    print(f"\n\nSolicitando respuesta para {inferencias}...\n")


    with open(kb, "r", encoding="utf-8") as f:
            data = json.load(f)

    if tema == "musica" or tema =="medicina":

        respuesta = random.choice(data.get("request", {}))

        for inferencia in inferencias:
            respuesta = respuesta + "\n - " + inferencia

    if tema == "tema general":

        prompt = inferencias
        mejor_score = 0

        for categoria, subcategorias in data.items():
            for subcat, contenido in subcategorias.items():
                for keyword in contenido.get("keywords", []):
                    score = similitud_semantica(prompt, keyword)
                    if score > mejor_score:
                        mejor_score = score
                        respuesta = contenido.get("respuesta", "No tengo respuesta definida")
    
    return respuesta
