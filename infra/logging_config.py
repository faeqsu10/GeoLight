"""GeoLight 구조화 로깅 설정."""

import os
import logging
import logging.handlers

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
MAX_BYTES = 10 * 1024 * 1024  # 10MB
BACKUP_COUNT = 5


def setup_logging(level=logging.INFO) -> logging.Logger:
    """루트 geolight 로거를 설정하고 반환한다."""
    os.makedirs(LOG_DIR, exist_ok=True)

    logger = logging.getLogger("geolight")
    logger.setLevel(level)
    if logger.handlers:
        return logger  # 중복 등록 방지

    fmt = logging.Formatter(
        "[%(asctime)s] %(levelname)s %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 콘솔 핸들러
    console = logging.StreamHandler()
    console.setLevel(level)
    console.setFormatter(fmt)
    logger.addHandler(console)

    # 파일 핸들러 (RotatingFileHandler)
    file_handler = logging.handlers.RotatingFileHandler(
        os.path.join(LOG_DIR, "geolight.log"),
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    return logger
