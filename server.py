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

Consignes de progression stricte :
1. ÉTAPE 0 (Connexion / Attente) : Salue les joueurs de manière incisive et demande-leur de dire "DÉMARRER" quand ils sont prêts, puis de donner leurs prénoms et le nombre de manches.
2. ÉTAPE 1 ET SUIVANTES (Manches de jeu) :
   - Dès que le mot "DÉMARRER" ou les prénoms sont donnés, passe immédiatement à l'Étape 1.
   - Propose les choix de questions : "Direct comme ça" (6 pts), "Tête au carré" (4 pts), "Plan à 3" (3 pts) ou "À deux c'est bien" (1 pt).
   - Pour les matières scolaires (histoire, géo, sciences), adapte la rigueur au niveau de difficulté.
   - Pour les autres thèmes, utilise de la culture générale globale.
   - Laisse les joueurs échanger. RÈGLE ABSOLUE : N'évalue aucune réponse tant que tu n'as pas entendu "RIDEAU" !
3. COMMANDES SPÉCIALES :
   - "RIDEAU" : Valide la réponse, donne le résultat avec une vanne et enchaîne sur l'étape/manche suivante.
   - "LOOPING" : Annule la question en cours sans points et tire une nouvelle question de replacement.
   - "TU VAS OÙ SANS CASQUE" : Gère la contestation (+2 pts si fondée, -2 pts et vanne si injustifiée).
"""

@app.get("/")
async def get_index():
    with open("index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
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
        async with client.aio.live.connect(model="gemini-2.0-flash-exp", config=config) as session:
            
            # Déclenchement automatique du salut de Jean-Luc à la connexion
            await session.send(input="Connexion établie. Jean-Luc, salue les cobayes et demande-leur de dire DÉMARRER !", end_of_turn=True)

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
                                    await websocket.send_bytes(part.inline_data.data)
                except Exception as e:
                    print(f"Erreur flux Gemini : {e}")

            await asyncio.gather(client_to_gemini(), gemini_to_client())

    except Exception as e:
        print(f"Erreur session Live : {e}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
