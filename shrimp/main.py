# Entry point factory for building the FastAPI app
from datetime import date
from functools import partial
import logging
import os
from pathlib import Path
from typing import Any, Mapping, Optional
from fastapi import FastAPI

from shrimp.app import create_app
from shrimp.conversation import Conversation
from shrimp.messages import use as use_language
from shrimp.messenger import GraphTransport, MessengerConfig, create_messenger_router
from shrimp.render import render_reply
from shrimp.reply_text import dashboard_reply, template_reply
from shrimp.sam import make_sam_segmenter
from shrimp.service import Service
from shrimp.sizing import SizeTable
from shrimp.pricing import PriceTable
from shrimp.spark import SparkWriter
from shrimp.store import Store

logger = logging.getLogger(__name__)


def read_setting(
    name: str,
    root: Optional[Path] = None,
    env: Optional[Mapping[str, str]] = None,
) -> Optional[str]:
    # Read setting from environment mapping or fallback to .env in root
    source_env = os.environ if env is None else env
    val = source_env.get(name)
    if val is not None:
        return val

    repo_root = root if root is not None else Path(__file__).resolve().parent.parent
    env_file = repo_root / ".env"
    if env_file.exists():
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, value = line.split("=", 1)
                    if key.strip() == name:
                        return value.strip().strip("\"'")
    return None


def _show_app_logs() -> None:
    # uvicorn only configures its own loggers: give the app's INFO lines a console handler
    app_logger = logging.getLogger("shrimp")
    app_logger.setLevel(logging.INFO)
    if not app_logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(levelname)s:     %(name)s: %(message)s"))
        app_logger.addHandler(handler)


def build(
    root: Optional[Path] = None,
    env: Optional[Mapping[str, str]] = None,
    segmenter: Optional[Any] = None,
    executor: Optional[Any] = None,
) -> FastAPI:
    # Build FastAPI app with service and optional Messenger bot router
    _show_app_logs()
    repo_root = root if root is not None else Path(__file__).resolve().parent.parent
    # BOT_LANG=en makes the bot speak English (for the demo); the default is Vietnamese
    language = (read_setting("BOT_LANG", root=repo_root, env=env) or "vi").strip().lower()
    use_language(language)
    api_key = read_setting("META_API_KEY", root=repo_root, env=env)

    if not api_key:
        raise RuntimeError("META_API_KEY is required but not found in environment or .env file")

    if segmenter is None:
        decode_script = repo_root / "node" / "decode.mjs"
        cache_dir = repo_root / "data" / "cache"
        segmenter = make_sam_segmenter(
            api_key=api_key,
            decode_script=str(decode_script),
            cache_dir=str(cache_dir),
        )

    db_path = repo_root / "data" / "shrimp.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    store = Store(db_path)

    table_path = repo_root / "shrimp" / "size_table.json"
    if not table_path.exists():
        table_path = Path(__file__).resolve().parent / "size_table.json"
    table = SizeTable.load(table_path)

    price_path = repo_root / "shrimp" / "price_table.json"
    if not price_path.exists():
        price_path = Path(__file__).resolve().parent / "price_table.json"
    price_table = PriceTable.load(price_path)

    photos_dir = repo_root / "data" / "photos"
    photos_dir.mkdir(parents=True, exist_ok=True)
    service = Service(segmenter, store, table, photos_dir=photos_dir, prices=price_table)
    store.seed_demo(date.today())
    app = create_app(service)

    page_token = read_setting("MESSENGER_PAGE_TOKEN", root=repo_root, env=env)
    app_secret = read_setting("MESSENGER_APP_SECRET", root=repo_root, env=env)
    verify_token = read_setting("MESSENGER_VERIFY_TOKEN", root=repo_root, env=env)

    if page_token and app_secret and verify_token:
        allowed_raw = read_setting("MESSENGER_ALLOWED_IDS", root=repo_root, env=env) or ""
        allowed_ids = frozenset(
            item.strip() for item in allowed_raw.split(",") if item.strip()
        )
        dashboard_url = read_setting("DASHBOARD_URL", root=repo_root, env=env)
        if dashboard_url is not None:
            dashboard_url = dashboard_url.strip() or None

        transport = GraphTransport(page_token)
        config = MessengerConfig(
            verify_token=verify_token,
            app_secret=app_secret,
            allowed_ids=allowed_ids,
        )
        # Reply after photo always uses template_reply (fast, no model call);
        # SPARK_REPLIES=1 lets Muse Spark write only the status (write_status).
        write_reply = template_reply
        write_status = dashboard_reply
        if read_setting("SPARK_REPLIES", root=repo_root, env=env) == "1":
            if language == "vi":
                spark = SparkWriter(api_key)
                write_status = spark.write_status
            else:
                logger.info("SPARK_REPLIES is Vietnamese only; the %s bot uses the plain status text", language)
        conversation = Conversation(
            service,
            transport,
            render=render_reply,
            render_left_out=partial(render_reply, show="left_out"),
            write_reply=write_reply,
            write_status=write_status,
            dashboard_url=dashboard_url,
        )
        router = create_messenger_router(
            config,
            conversation.handle,
            executor=executor,
        )
        app.include_router(router)
        logger.info("Messenger enabled (%d allowed ids)", len(allowed_ids))
    else:
        logger.info("Messenger disabled (0 allowed ids)")

    return app
