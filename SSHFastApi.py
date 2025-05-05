from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import asyncio
import asyncssh
import json

app = FastAPI()

async def ssh_handler(websocket: WebSocket):
    try:
        # Receive credentials from client
        credentials_json = await websocket.receive_text()
        creds = json.loads(credentials_json)

        ssh_host = creds.get("host")
        ssh_user = creds.get("user")
        ssh_password = creds.get("password")

        async with asyncssh.connect(
            ssh_host,
            username=ssh_user,
            password=ssh_password,
            known_hosts=None
        ) as conn:
            session = await conn.create_process(term_type="xterm")

            await websocket.send_text(f"Connected to {ssh_host} as {ssh_user}!\r\n")

            async def read_ssh_output():
                while not session.stdout.at_eof():
                    data = await session.stdout.read(1024)
                    if data:
                        await websocket.send_text(data)

            output_task = asyncio.create_task(read_ssh_output())

            try:
                while True:
                    data = await websocket.receive_text()
                    session.stdin.write(data)
                    await session.stdin.drain()
            except WebSocketDisconnect:
                output_task.cancel()
                await websocket.close()
            except Exception as e:
                output_task.cancel()
                await websocket.send_text(f"Error: {str(e)}")
                await websocket.close()

    except Exception as e:
        await websocket.send_text(f"SSH connection error: {str(e)}")
        await websocket.close()


@app.websocket("/ws/ssh")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    await ssh_handler(websocket)
