"""Readable worker failures, without leaking protocol messages into the UI."""


def worker_error(lines, language='en'):
    diagnostic = '\n'.join(line for line in lines if not line.startswith('STEM_EVENT ')).strip()
    if 'out of memory' in diagnostic.lower() and 'llvm' in diagnostic.lower():
        return ('Не хватило оперативной памяти при подготовке GPU-модели. Закрой тяжёлые приложения и повтори, '
                'или выбери фрагмент 6 секунд.' if language == 'ru' else
                'Not enough system memory while preparing the GPU model. Close memory-heavy apps and retry, '
                'or select a six-second chunk.')
    return diagnostic[-5000:] or ('Обработчик неожиданно завершился.' if language == 'ru' else 'The worker exited unexpectedly.')
