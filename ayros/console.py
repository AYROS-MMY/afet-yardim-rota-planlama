"""Komut satırı çıktısının her Windows konsolunda çalışmasını sağlar."""

import sys


def safe_console():
    """Konsolun karşılayamadığı Türkçe karakterlerde çökmek yerine '?' yazdır.

    Türkçe Windows (cp857) ve UTF-8 konsollarında çıktı değişmez. İngilizce
    Windows (cp1252) gibi konsollarda 'ı', 'ş', 'ğ' yüzünden UnicodeEncodeError
    oluşmasını önler.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass
