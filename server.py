import os
import asyncio
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from google import genai
from google.genai import types

app = FastAPI()

API_KEY = os.environ.get("GEMINI_API_KEY", "AQ.Ab8RN6KX94n07BM31htZqTRxwNAzLkP7hnsYkbL_JHW_49NDTg")

SYSTEM_PROMPT = """
Tu es Jean-Luc Deshman, l'animateur cynique, franc, sarcastique et pince-sans-rire du jeu "Les Idiots du Village".
Tu animes la partie en direct avec la voix. 

Consignes :
1. Sois incisif, drôle, mordant et percutant.
2. Salue immédiatement les cobayes, demande-leur le nombre de manches qu'ils veulent et leurs prénoms.
3. Attends impérativement le mot "RIDEAU" avant de valider une réponse.
4. Gère "LOOPING" (annuler la question) et "TU VAS OÙ SANS CASQUE" (contestation avec bonus/malus).
"""

@app.get("/")
async def get_index():
    with open("index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    # Utilisation du client officiel v1alpha
    client = genai.Client(api_key=API_KEY, http_options={'api_version': 'v1alpha'})
    
    config = types.LiveConnectConfig(
        response_modalities=[types.LiveModality.AUDIO],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Puck")
            )
        ),
        system_instruction=types.Content(parts=[types.Part.from_text(SYSTEM_PROMPT)])
    )

    try:
        # Modèle officiel Gemini 2.0 Flash Exp pour le flux Bidi Live
        async with client.aio.live.connect(model="gemini-2.0-flash-exp", config=config) as session:
            
            # Déclencheur vocal : On envoie un premier tour pour forcer Jean-Luc à saluer
            await session.send(input="Bonjour Jean-Luc, lance la partie !", end_of_turn=True)

            async def client_to_gemini():
                try:
                    while True:
                        data = await websocket.receive_bytes()
                        await session.send(input={"data": data, "mime_type": "audio/pcm"}, end_of_turn=False)
                except WebSocketDisconnect:
                    pass

            async def gemini_to_client():
                try:
                    async for response in session.receive():
                        server_content = response.server_content
                        if server_content and server_content.model_turn:
                            for part in server_content.model_turn.parts:
                                if part.inline_data and part.inline_data.data:
                                    # Envoi du flux audio binaire au client web
                                    await websocket.send_bytes(part.inline_data.data)
                except Exception as e:
                    print(f"Erreur flux Gemini : {e}")

            await asyncio.gather(client_to_gemini(), gemini_to_client())

    except Exception as e:
        print(f"Erreur session Live : {e}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
