import builtins

import logger


def test_no_config_reread(monkeypatch):
    """writeLog must not re-open config.yml; the level is cached at import."""
    real_open = builtins.open
    counter = {"config_opens": 0}

    def counting_open(file, *args, **kwargs):
        if "config.yml" in str(file):
            counter["config_opens"] += 1
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", counting_open)

    for _ in range(3):
        logger.writeLog("msg", "INFO", writeTofile=False)

    assert counter["config_opens"] == 0, (
        f"writeLog re-read config.yml {counter['config_opens']} times; expected 0"
    )
