"""Launch the isolated demo API without changing backend/.env."""
import os
from pathlib import Path
import sys

from dotenv import dotenv_values
import uvicorn


if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    config = dotenv_values(Path(__file__).with_name('.env'))
    if config.get('DB_HOST') != '127.0.0.1' or config.get('DB_NAME') != 'ecs':
        raise SystemExit('Expected the local ecs configuration; API was not started.')
    os.environ.update({key: value for key, value in config.items() if value is not None})
    os.environ.update(SCHEDULER_ENABLED='false', PAYROLL_SCHEDULER_ENABLED='false')
    if '--check-config' in sys.argv:
        from app.core.config import get_settings
        settings = get_settings()
        print(f'Demo target: {settings.db_host}:{settings.db_port}/{settings.db_name}; MAIL_ENABLED={str(settings.mail_enabled).lower()}; schedulers disabled.')
        raise SystemExit(0)
    uvicorn.run('app.main:app', host='127.0.0.1', port=8001)
