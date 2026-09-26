import asyncio
import json
import os
import subprocess
import time
import urllib.request
import base64
import websockets

scratch_dir = r"C:\Users\hp\.gemini\antigravity\brain\3f48bcf7-4e03-4df1-a415-66e8c7a611c3\scratch"
os.makedirs(scratch_dir, exist_ok=True)

chrome_exe = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
port = 9222

async def run():
    cmd = [
        chrome_exe,
        "--headless=new",
        f"--remote-debugging-port={port}",
        "--window-size=1440,900",
        "--autoplay-policy=no-user-gesture-required",
        "http://localhost:5173/",
    ]
    proc = subprocess.Popen(cmd)
    time.sleep(2.5)

    try:
        req = urllib.request.urlopen(f"http://localhost:{port}/json")
        tabs = json.loads(req.read().decode())
        target = [t for t in tabs if t.get("type") == "page"][0]
        ws_url = target["webSocketDebuggerUrl"]
        print(f"Connecting to CDP at {ws_url}")

        async with websockets.connect(ws_url, max_size=25 * 1024 * 1024) as ws:
            msg_id = 1

            async def send(method, params=None):
                nonlocal msg_id
                msg_id += 1
                payload = {"id": msg_id, "method": method}
                if params:
                    payload["params"] = params
                await ws.send(json.dumps(payload))
                while True:
                    resp = json.loads(await ws.recv())
                    if resp.get("id") == payload["id"]:
                        return resp.get("result", {})

            # Enable Page and Runtime
            await send("Page.enable")
            await send("Runtime.enable")

            # Wait 4.5 seconds for video reveal
            print("Waiting for landing reveal...")
            await asyncio.sleep(4.5)

            # Capture Landing Screenshot
            res = await send("Page.captureScreenshot", {"format": "png"})
            landing_path = os.path.join(scratch_dir, "landing_view.png")
            with open(landing_path, "wb") as f:
                f.write(base64.b64decode(res["data"]))
            print(f"Captured: {landing_path}")

            # Click ENTER COMMAND CENTER button
            print("Clicking ENTER COMMAND CENTER...")
            eval_res = await send(
                "Runtime.evaluate",
                {
                    "expression": """
                    (() => {
                        const btn = document.querySelector('[data-testid=\"deploy-btn\"]') || Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('ENTER COMMAND CENTER'));
                        if (btn) {
                            btn.click();
                            return 'clicked';
                        }
                        return 'not found';
                    })()
                """
                },
            )
            print("Click result:", eval_res)

            # Wait 2.5 seconds for dive transition into Command Center
            await asyncio.sleep(2.5)

            # Capture Command Center Screenshot
            res2 = await send("Page.captureScreenshot", {"format": "png"})
            cc_path = os.path.join(scratch_dir, "command_center_view.png")
            with open(cc_path, "wb") as f:
                f.write(base64.b64decode(res2["data"]))
            print(f"Captured: {cc_path}")

            # Click SCENARIO LAB Tab
            print("Switching to SCENARIO LAB...")
            await send(
                "Runtime.evaluate",
                {
                    "expression": """
                    (() => {
                        const btn = Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('SCENARIO LAB'));
                        if (btn) { btn.click(); return 'clicked'; }
                        return 'not found';
                    })()
                """
                },
            )
            await asyncio.sleep(1.2)

            # Capture Scenario Lab Screenshot
            res3 = await send("Page.captureScreenshot", {"format": "png"})
            scenario_path = os.path.join(scratch_dir, "scenario_lab_view.png")
            with open(scenario_path, "wb") as f:
                f.write(base64.b64decode(res3["data"]))
            print(f"Captured: {scenario_path}")

    finally:
        proc.terminate()

if __name__ == "__main__":
    asyncio.run(run())
