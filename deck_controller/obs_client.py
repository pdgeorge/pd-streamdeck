"""
obs-websocket v5 client with a supervised reconnect loop.

The streaming PC comes and goes; the Pi doesn't. So this holds an outbound
connection to OBS and quietly retries forever, rather than assuming OBS is
there. Everything the deck displays about OBS is kept current from OBS's own
events, which means the tablet stays honest even when you switch scenes from
the OBS window directly.
"""

import asyncio
import logging
from typing import Awaitable, Callable, Optional

import simpleobsws

LOGGER = logging.getLogger("deck.obs")

RECONNECT_MIN = 2
RECONNECT_MAX = 30


class ObsError(Exception):
    """A request failed, or OBS isn't connected."""


class ObsClient:
    def __init__(
        self,
        host: str,
        port: int,
        password: str,
        on_change: Callable[[], Awaitable[None]],
    ):
        self._url = f"ws://{host}:{port}"
        self._password = password
        self._on_change = on_change
        self._ws: Optional[simpleobsws.WebSocketClient] = None
        self._task: Optional[asyncio.Task] = None
        self._stopping = False

        # Mirrored OBS state. Read by the API, written only from events
        # and the post-connect refresh.
        self.connected = False
        self.current_scene: Optional[str] = None
        self.scenes: list[str] = []
        self.streaming = False
        self.recording = False
        self.muted: dict[str, bool] = {}
        self.last_error: Optional[str] = None

    # -- lifecycle ----------------------------------------------------------

    def start(self) -> None:
        self._task = asyncio.create_task(self._supervise(), name="obs-supervisor")

    async def stop(self) -> None:
        self._stopping = True
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await self._teardown()

    async def _supervise(self) -> None:
        backoff = RECONNECT_MIN
        while not self._stopping:
            try:
                await self._connect_once()
                backoff = RECONNECT_MIN
                # simpleobsws runs its own receive loop; poll identification
                # to notice the socket dropping.
                while self._ws and self._ws.is_identified():
                    await asyncio.sleep(2)
                LOGGER.warning("OBS connection lost")
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - retry on anything
                self.last_error = str(exc)
                LOGGER.info(
                    "OBS unreachable at %s (%s); retrying in %ss",
                    self._url, exc, backoff,
                )
            finally:
                if not self._stopping:
                    await self._mark_disconnected()

            if self._stopping:
                break
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, RECONNECT_MAX)

    async def _connect_once(self) -> None:
        await self._teardown()

        params = simpleobsws.IdentificationParameters(
            ignoreNonFatalRequestChecks=False
        )
        ws = simpleobsws.WebSocketClient(
            url=self._url, password=self._password, identification_parameters=params
        )

        for event, handler in (
            ("CurrentProgramSceneChanged", self._on_scene_changed),
            ("SceneListChanged", self._on_scene_list_changed),
            ("SceneNameChanged", self._on_scene_list_changed),
            ("StreamStateChanged", self._on_stream_state),
            ("RecordStateChanged", self._on_record_state),
            ("InputMuteStateChanged", self._on_input_mute),
        ):
            ws.register_event_callback(handler, event)

        await ws.connect()
        if not await ws.wait_until_identified(timeout=10):
            await ws.disconnect()
            raise ObsError("OBS refused identification (wrong password?)")

        self._ws = ws
        self.connected = True
        self.last_error = None
        LOGGER.info("Connected to OBS at %s", self._url)

        await self._refresh_all()
        await self._on_change()

    async def _teardown(self) -> None:
        if self._ws is not None:
            try:
                await self._ws.disconnect()
            except Exception:  # noqa: BLE001 - already going away
                pass
            self._ws = None

    async def _mark_disconnected(self) -> None:
        was_connected = self.connected
        self.connected = False
        await self._teardown()
        if was_connected:
            await self._on_change()

    # -- requests -----------------------------------------------------------

    async def call(self, request_type: str, data: Optional[dict] = None) -> dict:
        """Send one request. Raises ObsError rather than returning a sentinel,
        so a failed button press surfaces as an error on the tablet."""
        ws = self._ws
        if ws is None or not self.connected:
            raise ObsError("OBS is not connected")

        response = await ws.call(simpleobsws.Request(request_type, data or {}))
        if not response.ok():
            status = response.requestStatus
            comment = getattr(status, "comment", None) or getattr(status, "code", "")
            raise ObsError(f"{request_type} failed: {comment}")
        return response.responseData or {}

    async def _refresh_all(self) -> None:
        scene_list = await self.call("GetSceneList")
        self.scenes = [s["sceneName"] for s in scene_list.get("scenes", [])]
        self.current_scene = scene_list.get("currentProgramSceneName")

        try:
            self.streaming = bool(
                (await self.call("GetStreamStatus")).get("outputActive")
            )
            self.recording = bool(
                (await self.call("GetRecordStatus")).get("outputActive")
            )
        except ObsError as exc:
            LOGGER.warning("Could not read output status: %s", exc)

        # Prime mute state for every audio input so the tablet shows the
        # right thing before anything is toggled.
        try:
            inputs = (await self.call("GetInputList")).get("inputs", [])
            for item in inputs:
                name = item.get("inputName")
                if not name:
                    continue
                try:
                    result = await self.call("GetInputMute", {"inputName": name})
                    self.muted[name] = bool(result.get("inputMuted"))
                except ObsError:
                    # Non-audio inputs have no mute state; skip them.
                    continue
        except ObsError as exc:
            LOGGER.warning("Could not read input list: %s", exc)

    # -- high level actions -------------------------------------------------

    async def set_scene(self, scene: str) -> dict:
        await self.call("SetCurrentProgramScene", {"sceneName": scene})
        return {"scene": scene}

    async def toggle_source(
        self, source: str, scene: Optional[str] = None, visible: Optional[bool] = None
    ) -> dict:
        scene = scene or self.current_scene
        if not scene:
            raise ObsError("No scene given and no current scene known")

        item = await self.call(
            "GetSceneItemId", {"sceneName": scene, "sourceName": source}
        )
        item_id = item["sceneItemId"]

        if visible is None:
            current = await self.call(
                "GetSceneItemEnabled", {"sceneName": scene, "sceneItemId": item_id}
            )
            visible = not bool(current.get("sceneItemEnabled"))

        await self.call(
            "SetSceneItemEnabled",
            {"sceneName": scene, "sceneItemId": item_id, "sceneItemEnabled": visible},
        )
        return {"scene": scene, "source": source, "visible": visible}

    async def set_mute(self, input_name: str, muted: Optional[bool] = None) -> dict:
        if muted is None:
            result = await self.call("ToggleInputMute", {"inputName": input_name})
        else:
            await self.call(
                "SetInputMute", {"inputName": input_name, "inputMuted": muted}
            )
            result = {"inputMuted": muted}
        state = bool(result.get("inputMuted"))
        self.muted[input_name] = state
        return {"input": input_name, "muted": state}

    async def set_filter(
        self, source: str, filter_name: str, enabled: Optional[bool] = None
    ) -> dict:
        if enabled is None:
            current = await self.call(
                "GetSourceFilter", {"sourceName": source, "filterName": filter_name}
            )
            enabled = not bool(current.get("filterEnabled"))
        await self.call(
            "SetSourceFilterEnabled",
            {
                "sourceName": source,
                "filterName": filter_name,
                "filterEnabled": enabled,
            },
        )
        return {"source": source, "filter": filter_name, "enabled": enabled}

    async def output(self, kind: str, mode: str = "toggle") -> dict:
        """kind is 'stream' or 'record'."""
        verb = {"start": "Start", "stop": "Stop", "toggle": "Toggle"}.get(mode)
        if verb is None:
            raise ObsError(f"Unknown mode {mode!r} (use start, stop or toggle)")
        noun = "Stream" if kind == "stream" else "Record"
        await self.call(f"{verb}{noun}")
        return {"output": kind, "mode": mode}

    # -- event handlers -----------------------------------------------------

    async def _on_scene_changed(self, data: dict) -> None:
        self.current_scene = data.get("sceneName")
        await self._on_change()

    async def _on_scene_list_changed(self, _data: dict) -> None:
        try:
            scene_list = await self.call("GetSceneList")
            self.scenes = [s["sceneName"] for s in scene_list.get("scenes", [])]
            self.current_scene = scene_list.get("currentProgramSceneName")
        except ObsError as exc:
            LOGGER.warning("Scene list refresh failed: %s", exc)
        await self._on_change()

    async def _on_stream_state(self, data: dict) -> None:
        self.streaming = bool(data.get("outputActive"))
        await self._on_change()

    async def _on_record_state(self, data: dict) -> None:
        self.recording = bool(data.get("outputActive"))
        await self._on_change()

    async def _on_input_mute(self, data: dict) -> None:
        name = data.get("inputName")
        if name:
            self.muted[name] = bool(data.get("inputMuted"))
            await self._on_change()

    # -- snapshot -----------------------------------------------------------

    def snapshot(self) -> dict:
        return {
            "connected": self.connected,
            "current_scene": self.current_scene,
            "scenes": self.scenes,
            "streaming": self.streaming,
            "recording": self.recording,
            "muted": self.muted,
            "error": self.last_error if not self.connected else None,
        }
