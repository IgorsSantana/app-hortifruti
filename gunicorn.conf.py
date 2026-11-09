"""O Render inicia com gunicorn app:app e carrega este arquivo automaticamente."""


def on_starting(server):
    from schedule_update import run_schedule_update
    run_schedule_update()
