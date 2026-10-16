from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

from app.config import Config
from app.core import clock
from app.core.db import connect

ANNUAL_PLAN_YEAR = Config.ANNUAL_PLAN_YEAR

# Conquistas: cada uma tem um predicado sobre o contexto agregado de leitura.
# O contexto expoe: total_chapters, best_streak, current_streak, completed_plans.
ACHIEVEMENTS = (
    {"codigo": "primeiro_capitulo", "nome": "Primeiro Passo", "icone": "",
     "descricao": "Leia seu primeiro capitulo",
     "meta": lambda c: c["total_chapters"] >= 1},
    {"codigo": "dez_capitulos", "nome": "Aquecendo", "icone": "",
     "descricao": "Leia 10 capitulos",
     "meta": lambda c: c["total_chapters"] >= 10},
    {"codigo": "cinquenta_capitulos", "nome": "Constante", "icone": "",
     "descricao": "Leia 50 capitulos",
     "meta": lambda c: c["total_chapters"] >= 50},
    {"codigo": "cem_capitulos", "nome": "Centenario", "icone": "",
     "descricao": "Leia 100 capitulos",
     "meta": lambda c: c["total_chapters"] >= 100},
    {"codigo": "streak_3", "nome": "Pegando o Ritmo", "icone": "",
     "descricao": "Leia em 3 dias seguidos",
     "meta": lambda c: c["best_streak"] >= 3},
    {"codigo": "streak_7", "nome": "Semana de Fogo", "icone": "",
     "descricao": "Leia em 7 dias seguidos",
     "meta": lambda c: c["best_streak"] >= 7},
    {"codigo": "streak_30", "nome": "Disciplina de Ferro", "icone": "",
     "descricao": "Leia em 30 dias seguidos",
     "meta": lambda c: c["best_streak"] >= 30},
    {"codigo": "nt_completo", "nome": "Novo Testamento", "icone": "",
     "descricao": "Conclua o plano do Novo Testamento",
     "meta": lambda c: "novo_testamento" in c["completed_plans"]},
    {"codigo": "at_completo", "nome": "Antigo Testamento", "icone": "",
     "descricao": "Conclua o plano do Antigo Testamento",
     "meta": lambda c: "antigo_testamento" in c["completed_plans"]},
    {"codigo": "biblia_ano", "nome": "Biblia em um Ano", "icone": "",
     "descricao": "Conclua a Porcao Diaria",
     "meta": lambda c: "porcao_diaria" in c["completed_plans"]},
)


def _runs(numbers: list[int]) -> list[str]:
    """[5, 6, 7, 9] -> ["5-7", "9"]"""
    runs: list[str] = []
    start = prev = None
    for number in sorted(set(numbers)):
        if start is None:
            start = prev = number
        elif number == prev + 1:
            prev = number
        else:
            runs.append(str(start) if start == prev else f"{start}–{prev}")
            start = prev = number
    if start is not None:
        runs.append(str(start) if start == prev else f"{start}–{prev}")
    return runs


def chapters_label(chapters: list[dict[str, Any]]) -> str:
    """Capitulos por extenso: "Mateus 5–7" ou "Mateus 28 · Marcos 1"."""
    order: list[str] = []
    by_book: dict[str, list[int]] = {}
    for chapter in chapters:
        if chapter["livro"] not in by_book:
            order.append(chapter["livro"])
            by_book[chapter["livro"]] = []
        by_book[chapter["livro"]].append(chapter["capitulo"])
    return " · ".join(f"{book} {', '.join(_runs(by_book[book]))}" for book in order)


class ReadingPlanRepository:
    """SQLite access layer for reading plans, progress, notes, and statistics."""

    def __init__(self, bible: list[dict[str, Any]], db_path: Path) -> None:
        self.bible = bible
        self.db_path = Path(db_path)
        # (abbrev, capitulo) -> numero de versiculos; valida referencias e
        # permite somar versiculos lidos sem contar o mesmo capitulo duas vezes.
        self._verse_counts: dict[tuple[str, int], int] = {
            (book["abbrev"], number): len(verses)
            for book in bible
            for number, verses in enumerate(book["chapters"], start=1)
        }
        self._canonical_abbrev = {book["abbrev"].lower(): book["abbrev"] for book in bible}
        self.old_testament = self._flatten_books(bible[:39], "Antigo Testamento")
        self.new_testament = self._flatten_books(bible[39:], "Novo Testamento")
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        return connect(self.db_path)

    def _initialize(self) -> None:
        with self._connect() as connection:
            self._create_tables(connection)
            self._seed_plans(connection)

    def _create_tables(self, connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS reading_plans (
                id INTEGER PRIMARY KEY,
                nome TEXT NOT NULL,
                tipo TEXT NOT NULL UNIQUE,
                total_dias INTEGER NOT NULL,
                assinatura TEXT,
                criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS reading_progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plano_id INTEGER NOT NULL,
                dia INTEGER NOT NULL,
                ordem INTEGER NOT NULL,
                livro TEXT NOT NULL,
                abbrev TEXT NOT NULL,
                capitulo INTEGER NOT NULL,
                testamento TEXT NOT NULL,
                versiculos INTEGER NOT NULL,
                concluido INTEGER NOT NULL DEFAULT 0,
                data_conclusao TEXT,
                FOREIGN KEY (plano_id) REFERENCES reading_plans(id) ON DELETE CASCADE,
                UNIQUE (plano_id, livro, capitulo)
            );

            CREATE TABLE IF NOT EXISTS reading_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plano_id INTEGER NOT NULL,
                dia INTEGER NOT NULL,
                texto TEXT NOT NULL DEFAULT '',
                criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                atualizado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (plano_id) REFERENCES reading_plans(id) ON DELETE CASCADE,
                UNIQUE (plano_id, dia)
            );

            CREATE TABLE IF NOT EXISTS user_statistics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plano_id INTEGER NOT NULL UNIQUE,
                capitulos_lidos INTEGER NOT NULL DEFAULT 0,
                versiculos_lidos INTEGER NOT NULL DEFAULT 0,
                dias_consecutivos INTEGER NOT NULL DEFAULT 0,
                maior_sequencia INTEGER NOT NULL DEFAULT 0,
                tempo_total_lido INTEGER NOT NULL DEFAULT 0,
                ultimo_acesso TEXT,
                atualizado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (plano_id) REFERENCES reading_plans(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS reading_activity (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data TEXT NOT NULL UNIQUE
            );

            CREATE TABLE IF NOT EXISTS achievements (
                codigo TEXT PRIMARY KEY,
                desbloqueado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            -- Leituras fora de um plano (leitura livre). Entram na contagem global
            -- de capitulos lidos, na sequencia e no heatmap.
            CREATE TABLE IF NOT EXISTS free_reads (
                abbrev TEXT NOT NULL,
                capitulo INTEGER NOT NULL,
                data TEXT NOT NULL,
                lido_em TEXT NOT NULL,
                PRIMARY KEY (abbrev, capitulo, data)
            );

            CREATE TABLE IF NOT EXISTS plan_bookmarks (
                plano_id INTEGER PRIMARY KEY,
                dia INTEGER NOT NULL,
                atualizado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (plano_id) REFERENCES reading_plans(id) ON DELETE CASCADE
            );
            """
        )
        # Bancos criados antes da coluna `assinatura`.
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(reading_plans)")}
        if "assinatura" not in columns:
            connection.execute("ALTER TABLE reading_plans ADD COLUMN assinatura TEXT")

    def _seed_plans(self, connection: sqlite3.Connection) -> None:
        definitions = (
            {
                "id": 1,
                "nome": "Plano Novo Testamento",
                "tipo": "novo_testamento",
                "schedule": self._build_chunked_schedule(self.new_testament, 3),
            },
            {
                "id": 2,
                "nome": "Plano Antigo Testamento",
                "tipo": "antigo_testamento",
                "schedule": self._build_chunked_schedule(self.old_testament, 3),
            },
            {
                "id": 3,
                "nome": "Porção Diária",
                "tipo": "porcao_diaria",
                "schedule": self._build_daily_portion_schedule(),
            },
        )

        for plan in definitions:
            schedule = plan["schedule"]
            total_days = len(schedule)
            expected_count = sum(len(day) for day in schedule)
            signature = self._schedule_signature(schedule)

            existing = connection.execute(
                "SELECT assinatura FROM reading_plans WHERE id = ?", (plan["id"],)
            ).fetchone()
            connection.execute(
                """
                INSERT INTO reading_plans (id, nome, tipo, total_dias, assinatura)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    nome = excluded.nome,
                    tipo = excluded.tipo,
                    total_dias = excluded.total_dias,
                    assinatura = excluded.assinatura
                """,
                (plan["id"], plan["nome"], plan["tipo"], total_days, signature),
            )
            progress_count = connection.execute(
                "SELECT COUNT(*) AS n FROM reading_progress WHERE plano_id = ?", (plan["id"],)
            ).fetchone()["n"]

            # A assinatura (hash do cronograma inteiro) detecta qualquer mudanca de
            # layout — inclusive trocar ANNUAL_PLAN_YEAR com a mesma contagem.
            needs_rebuild = (
                existing is None
                or existing["assinatura"] != signature
                or progress_count != expected_count
            )
            if needs_rebuild:
                self._rebuild_schedule(connection, plan["id"], schedule)

            connection.execute(
                "INSERT OR IGNORE INTO user_statistics (plano_id) VALUES (?)",
                (plan["id"],),
            )
            self._refresh_statistics(connection, plan["id"])

    @staticmethod
    def _schedule_signature(schedule: list[list[dict[str, Any]]]) -> str:
        layout = [[(c["abbrev"], c["chapter"]) for c in day] for day in schedule]
        return hashlib.sha1(json.dumps(layout).encode()).hexdigest()

    def _rebuild_schedule(
        self,
        connection: sqlite3.Connection,
        plan_id: int,
        schedule: list[list[dict[str, Any]]],
    ) -> None:
        """Recria o cronograma PRESERVANDO o que o usuario ja leu (por livro+capitulo).
        As anotacoes por dia tambem sao mantidas."""
        done = {
            (row["livro"], row["capitulo"]): row["data_conclusao"]
            for row in connection.execute(
                """
                SELECT livro, capitulo, data_conclusao FROM reading_progress
                WHERE plano_id = ? AND concluido = 1
                """,
                (plan_id,),
            ).fetchall()
        }
        connection.execute("DELETE FROM reading_progress WHERE plano_id = ?", (plan_id,))
        self._insert_schedule(connection, plan_id, schedule)
        connection.executemany(
            """
            UPDATE reading_progress SET concluido = 1, data_conclusao = ?
            WHERE plano_id = ? AND livro = ? AND capitulo = ?
            """,
            [(when, plan_id, livro, capitulo) for (livro, capitulo), when in done.items()],
        )

    def _insert_schedule(
        self,
        connection: sqlite3.Connection,
        plan_id: int,
        schedule: list[list[dict[str, Any]]],
    ) -> None:
        rows = []
        for day_number, chapters in enumerate(schedule, start=1):
            for order, chapter in enumerate(chapters, start=1):
                rows.append(
                    (
                        plan_id,
                        day_number,
                        order,
                        chapter["book"],
                        chapter["abbrev"],
                        chapter["chapter"],
                        chapter["testament"],
                        chapter["verses"],
                    )
                )
        connection.executemany(
            """
            INSERT OR IGNORE INTO reading_progress
                (plano_id, dia, ordem, livro, abbrev, capitulo, testamento, versiculos)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )

    def _flatten_books(self, books: Iterable[dict[str, Any]], testament: str) -> list[dict[str, Any]]:
        chapters: list[dict[str, Any]] = []
        for book in books:
            for chapter_index, verses in enumerate(book["chapters"], start=1):
                chapters.append(
                    {
                        "book": book["name"],
                        "abbrev": book["abbrev"],
                        "chapter": chapter_index,
                        "testament": testament,
                        "verses": len(verses),
                    }
                )
        return chapters

    def _build_chunked_schedule(
        self,
        chapters: list[dict[str, Any]],
        chunk_size: int,
    ) -> list[list[dict[str, Any]]]:
        schedule: list[list[dict[str, Any]]] = []
        for index in range(0, len(chapters), chunk_size):
            schedule.append(chapters[index:index + chunk_size])
        return schedule

    def _build_daily_portion_schedule(self) -> list[list[dict[str, Any]]]:
        schedule: list[list[dict[str, Any]]] = []
        old_counts = self._daily_portion_old_testament_counts()
        old_index = 0
        new_index = 0

        for day_offset, old_count in enumerate(old_counts):
            current_date = datetime(ANNUAL_PLAN_YEAR, 1, 1).date() + timedelta(days=day_offset)
            day: list[dict[str, Any]] = []

            if current_date.weekday() < 5 and new_index < len(self.new_testament):
                day.append(self.new_testament[new_index])
                new_index += 1

            day.extend(self.old_testament[old_index:old_index + old_count])
            old_index += old_count
            schedule.append(day)

        return schedule

    def _daily_portion_old_testament_counts(self) -> list[int]:
        first_quarter = [
            3, 3, 3, 3, 3, 3, 3, 3, 2, 2, 2, 2, 3, 3, 2, 2,
            3, 3, 2, 3, 3, 2, 2, 2, 3, 3, 3, 3, 2, 2, 2,
            3, 3, 2, 2, 3, 3, 3, 3, 2, 3, 2, 2, 2, 2, 2,
            2, 2, 2, 2, 3, 3, 2, 3, 3, 3, 2, 2, 2,
            2, 3, 2, 2, 3, 3, 3, 3, 3, 3, 3, 2, 2, 2, 3,
            3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 2, 2, 2, 3, 3, 3,
        ]
        remaining_chapters = len(self.old_testament) - sum(first_quarter)
        remaining_days = 365 - len(first_quarter)
        return first_quarter + self._balanced_counts(remaining_chapters, remaining_days)

    def _balanced_counts(self, total: int, days: int) -> list[int]:
        base = total // days
        extra = total - (base * days)
        counts: list[int] = []
        carried = 0
        for _ in range(days):
            carried += extra
            count = base
            if carried >= days:
                count += 1
                carried -= days
            counts.append(count)
        return counts

    def list_plans(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            plans = connection.execute(
                "SELECT id, nome, tipo, total_dias FROM reading_plans ORDER BY id"
            ).fetchall()
            streak = self._calendar_streak(connection)  # igual para todos os planos
            return [self._plan_summary(connection, row, streak) for row in plans]

    def continue_reading(self) -> dict[str, Any] | None:
        """Onde o leitor parou, para a tela inicial: plano, dia e capitulos
        pendentes por extenso ("Mateus 5-7"). Sem numeros de progresso."""
        with self._connect() as connection:
            plans = connection.execute(
                "SELECT id, nome, total_dias FROM reading_plans ORDER BY id"
            ).fetchall()
            if not plans:
                return None
            candidates = []
            for plan in plans:
                progress = self._plan_progress(connection, plan["id"])
                done, total = progress["completed_chapters"], progress["total_chapters"]
                if done < total:  # ainda ha o que ler
                    candidates.append((plan, done, total))
            if not candidates:
                return None  # tudo concluido: a home mostra o convite padrao
            # Prefere o plano ja iniciado e mais adiantado; senao, o primeiro.
            started = [c for c in candidates if c[1] > 0]
            if started:
                plan, _done, _total = max(started, key=lambda c: c[1] / c[2])
            else:
                plan, _done, _total = candidates[0]
            iniciado = bool(started)

            day = self._effective_day(connection, plan["id"], plan["total_dias"])
            chapters = self._chapters_for_day(connection, plan["id"], day)
            pending = [c for c in chapters if not c["concluido"]] or chapters
            first = pending[0] if pending else None
            return {
                "plano_id": plan["id"],
                "nome": plan["nome"],
                "dia": day,
                "iniciado": iniciado,
                "capitulos": chapters_label(pending),
                "proximo": None if first is None else {
                    "abbrev": first["abbrev"],
                    "capitulo": first["capitulo"],
                    "rotulo": f"{first['livro']} {first['capitulo']}",
                },
            }

    def reading_overview(self) -> dict[str, Any]:
        """Agregados para o dashboard: totais, sequencia e sugestao de continuacao."""
        plans = self.list_plans()
        with self._connect() as connection:
            chapters, verses = self._read_totals(connection)
            streak = self._calendar_streak(connection)

        in_progress = [p for p in plans if 0 < p["progress"]["percent"] < 100]
        candidate = max(in_progress, key=lambda p: p["progress"]["percent"], default=None)
        if candidate is None:
            candidate = next((p for p in plans if p["progress"]["percent"] < 100), plans[0] if plans else None)

        continuar = None
        if candidate:
            continuar = {
                "plano_id": candidate["id"],
                "nome": candidate["nome"],
                "dia": candidate["current_day"],
                "total_dias": candidate["total_dias"],
                "percent": candidate["progress"]["percent"],
            }

        return {
            "plans": plans,
            "capitulos_lidos": chapters,
            "versiculos_lidos": verses,
            "tempo_total": self._estimate_minutes(verses),
            "sequencia_atual": streak["atual"],
            "melhor_sequencia": streak["melhor"],
            "continuar": continuar,
        }

    def growth_data(self, weeks: int = 26) -> dict[str, Any]:
        """Dados para o painel de crescimento (heatmap + evolucao semanal)."""
        with self._connect() as connection:
            # Um capitulo lido no mesmo dia conta uma vez, mesmo estando em varios planos.
            rows = connection.execute(
                """
                SELECT dia, COUNT(*) AS total FROM (
                    SELECT abbrev, capitulo, substr(data_conclusao, 1, 10) AS dia
                    FROM reading_progress
                    WHERE concluido = 1 AND data_conclusao IS NOT NULL
                    UNION
                    SELECT abbrev, capitulo, data AS dia FROM free_reads
                )
                GROUP BY dia
                """
            ).fetchall()
            streak = self._calendar_streak(connection)

        daily_counts = {row["dia"]: int(row["total"]) for row in rows if row["dia"]}
        today = clock.now().date()

        # Grade do heatmap: ultimas `weeks` semanas, comecando no domingo.
        start = today - timedelta(days=today.weekday() + 1 + (weeks - 1) * 7)
        if start.weekday() != 6:  # garante inicio no domingo
            start = start - timedelta(days=(start.weekday() + 1) % 7)
        heatmap: list[dict[str, Any]] = []
        cursor = start
        while cursor <= today:
            iso = cursor.isoformat()
            heatmap.append({"date": iso, "count": daily_counts.get(iso, 0)})
            cursor += timedelta(days=1)

        # Evolucao das ultimas 8 semanas.
        weekly: list[dict[str, Any]] = []
        for offset in range(7, -1, -1):
            week_start = today - timedelta(days=today.weekday() + offset * 7)
            total = sum(
                count
                for iso, count in daily_counts.items()
                if week_start <= datetime.strptime(iso, "%Y-%m-%d").date() < week_start + timedelta(days=7)
            )
            weekly.append({"label": week_start.strftime("%d/%m"), "total": total})

        return {
            "heatmap": heatmap,
            "weekly": weekly,
            "dias_lidos": len(daily_counts),
            "sequencia_atual": streak["atual"],
            "melhor_sequencia": streak["melhor"],
            "media_diaria": round(sum(daily_counts.values()) / len(daily_counts), 1) if daily_counts else 0,
        }

    def get_plan_day(self, plan_id: int, day: int | None = None) -> dict[str, Any] | None:
        with self._connect() as connection:
            plan = connection.execute(
                "SELECT id, nome, tipo, total_dias FROM reading_plans WHERE id = ?",
                (plan_id,),
            ).fetchone()
            if plan is None:
                return None

            if day is None:
                selected_day = self._effective_day(connection, plan_id, plan["total_dias"])
            else:
                selected_day = max(1, min(int(day), plan["total_dias"]))
                self._set_bookmark(connection, plan_id, selected_day)
            chapters = self._chapters_for_day(connection, plan_id, selected_day)
            note = connection.execute(
                "SELECT texto FROM reading_notes WHERE plano_id = ? AND dia = ?",
                (plan_id, selected_day),
            ).fetchone()
            progress = self._plan_progress(connection, plan_id)
            statistics = self._statistics(connection, plan_id, progress=progress)
            day_verses = sum(chapter["versiculos"] for chapter in chapters)
            day_completed = bool(chapters) and all(chapter["concluido"] for chapter in chapters)
            first_pending = next((chapter for chapter in chapters if not chapter["concluido"]), None)
            is_daily_portion = plan["tipo"] == "porcao_diaria"
            calendar_date = self._daily_portion_date(selected_day) if is_daily_portion else None
            has_new_testament = any(chapter["testamento"] == "Novo Testamento" for chapter in chapters)

            return {
                "plan": dict(plan),
                "day": selected_day,
                "current_day": self._effective_day(connection, plan_id, plan["total_dias"]),
                "chapters": chapters,
                "calendar_label": self._format_daily_portion_date(calendar_date) if calendar_date else "",
                "has_free_main_reading": is_daily_portion and not has_new_testament,
                "note": note["texto"] if note else "",
                "statistics": statistics,
                "day_completed": day_completed,
                "first_pending": first_pending,
                "estimated_minutes": self._estimate_minutes(day_verses),
                "progress": progress,
            }

    def update_progress(
        self,
        plan_id: int,
        book: str,
        chapter: int,
        completed: bool,
    ) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id, dia FROM reading_progress
                WHERE plano_id = ? AND livro = ? AND capitulo = ?
                """,
                (plan_id, book, chapter),
            ).fetchone()
            if row is None:
                return None

            completed_at = clock.now().isoformat(timespec="seconds") if completed else None
            connection.execute(
                """
                UPDATE reading_progress
                SET concluido = ?, data_conclusao = ?
                WHERE id = ?
                """,
                (1 if completed else 0, completed_at, row["id"]),
            )
            if completed:
                self._record_activity(connection)
            self._touch_statistics(connection, plan_id)
            self._refresh_statistics(connection, plan_id)
            newly_codes = self._sync_achievements(connection)
            day_completed = self._day_completed(connection, plan_id, row["dia"])
            return {
                "day": row["dia"],
                "day_completed": day_completed,
                "progress": self._plan_progress(connection, plan_id),
                "statistics": self._statistics(connection, plan_id),
                "new_achievements": [
                    achievement
                    for achievement in (self._achievement_by_code(code) for code in newly_codes)
                    if achievement is not None
                ],
            }

    def save_note(self, plan_id: int, day: int, text: str) -> dict[str, Any] | None:
        now = clock.now().isoformat(timespec="seconds")
        with self._connect() as connection:
            plan = connection.execute(
                "SELECT total_dias FROM reading_plans WHERE id = ?",
                (plan_id,),
            ).fetchone()
            if plan is None or not (1 <= day <= plan["total_dias"]):
                return None
            connection.execute(
                """
                INSERT INTO reading_notes (plano_id, dia, texto, criado_em, atualizado_em)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(plano_id, dia) DO UPDATE SET
                    texto = excluded.texto,
                    atualizado_em = excluded.atualizado_em
                """,
                (plan_id, day, text, now, now),
            )
            self._touch_statistics(connection, plan_id)
            return {"saved": True, "updated_at": now}

    def get_statistics_page(self, plan_id: int) -> dict[str, Any] | None:
        with self._connect() as connection:
            plan = connection.execute(
                "SELECT id, nome, tipo, total_dias FROM reading_plans WHERE id = ?",
                (plan_id,),
            ).fetchone()
            if plan is None:
                return None
            self._refresh_statistics(connection, plan_id)
            return {
                "plan": dict(plan),
                "statistics": self._statistics(connection, plan_id),
                "progress": self._plan_progress(connection, plan_id),
                "current_day": self._effective_day(connection, plan_id, plan["total_dias"]),
            }

    def _plan_summary(
        self, connection: sqlite3.Connection, plan: sqlite3.Row, streak: dict[str, int] | None = None
    ) -> dict[str, Any]:
        progress = self._plan_progress(connection, plan["id"])
        statistics = self._statistics(connection, plan["id"], progress=progress, streak=streak)
        return {
            **dict(plan),
            "progress": progress,
            "statistics": statistics,
            "current_day": self._effective_day(connection, plan["id"], plan["total_dias"]),
        }

    def _chapters_for_day(
        self,
        connection: sqlite3.Connection,
        plan_id: int,
        day: int,
    ) -> list[dict[str, Any]]:
        rows = connection.execute(
            """
            SELECT id, dia, ordem, livro, abbrev, capitulo, testamento, versiculos,
                   concluido, data_conclusao
            FROM reading_progress
            WHERE plano_id = ? AND dia = ?
            ORDER BY ordem
            """,
            (plan_id, day),
        ).fetchall()
        return [{**dict(row), "concluido": bool(row["concluido"])} for row in rows]

    def _current_day(self, connection: sqlite3.Connection, plan_id: int, total_days: int) -> int:
        """Primeiro dia com capitulos pendentes (metrica de progresso real)."""
        row = connection.execute(
            """
            SELECT dia
            FROM reading_progress
            WHERE plano_id = ?
            GROUP BY dia
            HAVING SUM(CASE WHEN concluido = 1 THEN 1 ELSE 0 END) < COUNT(*)
            ORDER BY dia
            LIMIT 1
            """,
            (plan_id,),
        ).fetchone()
        return row["dia"] if row else total_days

    def _get_bookmark(self, connection: sqlite3.Connection, plan_id: int) -> int | None:
        row = connection.execute(
            "SELECT dia FROM plan_bookmarks WHERE plano_id = ?", (plan_id,)
        ).fetchone()
        return row["dia"] if row else None

    def _set_bookmark(self, connection: sqlite3.Connection, plan_id: int, day: int) -> None:
        connection.execute(
            """
            INSERT INTO plan_bookmarks (plano_id, dia, atualizado_em)
            VALUES (?, ?, datetime('now'))
            ON CONFLICT(plano_id) DO UPDATE SET dia = excluded.dia, atualizado_em = excluded.atualizado_em
            """,
            (plan_id, day),
        )

    def _effective_day(self, connection: sqlite3.Connection, plan_id: int, total_days: int) -> int:
        """Dia a mostrar por padrao: o marcador definido pelo usuario, senao o primeiro pendente."""
        bookmark = self._get_bookmark(connection, plan_id)
        if bookmark is not None:
            return max(1, min(bookmark, total_days))
        return self._current_day(connection, plan_id, total_days)

    def _day_completed(self, connection: sqlite3.Connection, plan_id: int, day: int) -> bool:
        row = connection.execute(
            """
            SELECT COUNT(*) AS total, SUM(CASE WHEN concluido = 1 THEN 1 ELSE 0 END) AS done
            FROM reading_progress
            WHERE plano_id = ? AND dia = ?
            """,
            (plan_id, day),
        ).fetchone()
        return bool(row and row["total"] and row["total"] == row["done"])

    def _plan_progress(self, connection: sqlite3.Connection, plan_id: int) -> dict[str, Any]:
        row = connection.execute(
            """
            SELECT
                COUNT(*) AS total_chapters,
                SUM(CASE WHEN concluido = 1 THEN 1 ELSE 0 END) AS completed_chapters,
                SUM(versiculos) AS total_verses,
                SUM(CASE WHEN concluido = 1 THEN versiculos ELSE 0 END) AS completed_verses
            FROM reading_progress
            WHERE plano_id = ?
            """,
            (plan_id,),
        ).fetchone()
        total_chapters = int(row["total_chapters"] or 0)
        completed_chapters = int(row["completed_chapters"] or 0)
        total_verses = int(row["total_verses"] or 0)
        completed_verses = int(row["completed_verses"] or 0)
        percent = round((completed_chapters / total_chapters) * 100) if total_chapters else 0
        return {
            "total_chapters": total_chapters,
            "completed_chapters": completed_chapters,
            "remaining_chapters": max(total_chapters - completed_chapters, 0),
            "total_verses": total_verses,
            "completed_verses": completed_verses,
            "percent": percent,
        }

    def _statistics(
        self,
        connection: sqlite3.Connection,
        plan_id: int,
        progress: dict[str, Any] | None = None,
        streak: dict[str, int] | None = None,
    ) -> dict[str, Any]:
        row = connection.execute(
            """
            SELECT capitulos_lidos, versiculos_lidos, dias_consecutivos, maior_sequencia,
                   tempo_total_lido, ultimo_acesso
            FROM user_statistics
            WHERE plano_id = ?
            """,
            (plan_id,),
        ).fetchone()
        if row is None:
            connection.execute("INSERT OR IGNORE INTO user_statistics (plano_id) VALUES (?)", (plan_id,))
            row = connection.execute(
                "SELECT * FROM user_statistics WHERE plano_id = ?",
                (plan_id,),
            ).fetchone()

        progress = progress or self._plan_progress(connection, plan_id)
        remaining_days = self._remaining_days(connection, plan_id)
        completion_date = clock.today() + timedelta(days=max(remaining_days - 1, 0))
        calendar_streak = streak or self._calendar_streak(connection)
        return {
            **dict(row),
            "capitulos_restantes": progress["remaining_chapters"],
            "porcentagem_plano": progress["percent"],
            "data_prevista_conclusao": completion_date.strftime("%d/%m/%Y"),
            "sequencia_calendario": calendar_streak["atual"],
            "melhor_sequencia_calendario": calendar_streak["melhor"],
        }

    def _refresh_statistics(self, connection: sqlite3.Connection, plan_id: int) -> None:
        progress = self._plan_progress(connection, plan_id)
        streak = self._completed_day_streak(connection, plan_id)
        reading_minutes = self._estimate_minutes(progress["completed_verses"])
        now = clock.now().isoformat(timespec="seconds")
        connection.execute(
            """
            UPDATE user_statistics
            SET capitulos_lidos = ?,
                versiculos_lidos = ?,
                dias_consecutivos = ?,
                maior_sequencia = MAX(maior_sequencia, ?),
                tempo_total_lido = ?,
                atualizado_em = ?
            WHERE plano_id = ?
            """,
            (
                progress["completed_chapters"],
                progress["completed_verses"],
                streak,
                streak,
                reading_minutes,
                now,
                plan_id,
            ),
        )

    def _touch_statistics(self, connection: sqlite3.Connection, plan_id: int) -> None:
        connection.execute(
            "UPDATE user_statistics SET ultimo_acesso = ? WHERE plano_id = ?",
            (clock.now().isoformat(timespec="seconds"), plan_id),
        )

    def _completed_day_streak(self, connection: sqlite3.Connection, plan_id: int) -> int:
        rows = connection.execute(
            """
            SELECT dia,
                   COUNT(*) AS total,
                   SUM(CASE WHEN concluido = 1 THEN 1 ELSE 0 END) AS done
            FROM reading_progress
            WHERE plano_id = ?
            GROUP BY dia
            ORDER BY dia
            """,
            (plan_id,),
        ).fetchall()
        streak = 0
        for row in rows:
            if row["total"] == row["done"]:
                streak += 1
            else:
                break
        return streak

    def _read_totals(self, connection: sqlite3.Connection) -> tuple[int, int]:
        """(capitulos, versiculos) lidos, contando cada capitulo UMA vez, mesmo que
        apareca em varios planos, e incluindo a leitura livre."""
        rows = connection.execute(
            """
            SELECT abbrev, capitulo FROM reading_progress WHERE concluido = 1
            UNION
            SELECT abbrev, capitulo FROM free_reads
            """
        ).fetchall()
        chapters = {(row["abbrev"], row["capitulo"]) for row in rows}
        verses = sum(self._verse_counts.get(key, 0) for key in chapters)
        return len(chapters), verses

    def read_chapters_of_book(self, abbrev: str) -> set[int]:
        """Numeros dos capitulos ja lidos de um livro (planos + leitura livre)."""
        canonical = self._canonical_abbrev.get(str(abbrev).lower())
        if canonical is None:
            return set()
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT capitulo FROM reading_progress WHERE concluido = 1 AND abbrev = ?
                UNION
                SELECT capitulo FROM free_reads WHERE abbrev = ?
                """,
                (canonical, canonical),
            ).fetchall()
        return {row["capitulo"] for row in rows}

    def mark_chapter_read(self, abbrev: str, chapter: int) -> dict[str, Any] | None:
        """Registra a leitura de um capitulo fora de plano (leitura livre).
        Retorna None se a referencia nao existe na Biblia."""
        canonical = self._canonical_abbrev.get(str(abbrev).lower())
        if canonical is None or (canonical, chapter) not in self._verse_counts:
            return None
        now = clock.now()
        with self._connect() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO free_reads (abbrev, capitulo, data, lido_em) VALUES (?, ?, ?, ?)",
                (canonical, chapter, now.date().isoformat(), now.isoformat(timespec="seconds")),
            )
            self._record_activity(connection)
            new_codes = self._sync_achievements(connection)
            total, _verses = self._read_totals(connection)
            return {
                "capitulos_lidos": total,
                "new_achievements": [
                    a for a in (self._achievement_by_code(code) for code in new_codes) if a is not None
                ],
            }

    def _record_activity(self, connection: sqlite3.Connection) -> None:
        today = clock.today().isoformat()
        connection.execute(
            "INSERT OR IGNORE INTO reading_activity (data) VALUES (?)",
            (today,),
        )

    def _activity_dates(self, connection: sqlite3.Connection) -> list:
        rows = connection.execute(
            "SELECT data FROM reading_activity ORDER BY data"
        ).fetchall()
        dates = []
        for row in rows:
            try:
                dates.append(datetime.strptime(row["data"], "%Y-%m-%d").date())
            except (ValueError, TypeError):
                continue
        return dates

    def _calendar_streak(self, connection: sqlite3.Connection) -> dict[str, int]:
        dates = self._activity_dates(connection)
        if not dates:
            return {"atual": 0, "melhor": 0}

        best = 1
        run = 1
        for previous, current in zip(dates, dates[1:]):
            if (current - previous).days == 1:
                run += 1
            elif current != previous:
                run = 1
            best = max(best, run)

        today = clock.now().date()
        last = dates[-1]
        gap = (today - last).days
        if gap > 1:
            current_streak = 0
        else:
            current_streak = 1
            for previous, current in zip(reversed(dates), reversed(dates[:-1])):
                if (previous - current).days == 1:
                    current_streak += 1
                else:
                    break
        return {"atual": current_streak, "melhor": best}

    def _achievement_context(self, connection: sqlite3.Connection) -> dict[str, Any]:
        total_chapters, _verses = self._read_totals(connection)
        completed_plans = connection.execute(
            """
            SELECT rp.tipo
            FROM reading_plans rp
            JOIN reading_progress rg ON rg.plano_id = rp.id
            GROUP BY rp.id
            HAVING SUM(CASE WHEN rg.concluido = 1 THEN 1 ELSE 0 END) = COUNT(*)
            """
        ).fetchall()
        streak = self._calendar_streak(connection)
        return {
            "total_chapters": total_chapters,
            "best_streak": streak["melhor"],
            "current_streak": streak["atual"],
            "completed_plans": {row["tipo"] for row in completed_plans},
        }

    def _sync_achievements(self, connection: sqlite3.Connection) -> list[str]:
        """Desbloqueia conquistas recem-conquistadas e retorna os codigos novos."""
        context = self._achievement_context(connection)
        unlocked = {
            row["codigo"]
            for row in connection.execute("SELECT codigo FROM achievements").fetchall()
        }
        newly: list[str] = []
        now = clock.now().isoformat(timespec="seconds")
        for achievement in ACHIEVEMENTS:
            if achievement["codigo"] in unlocked:
                continue
            if achievement["meta"](context):
                connection.execute(
                    "INSERT OR IGNORE INTO achievements (codigo, desbloqueado_em) VALUES (?, ?)",
                    (achievement["codigo"], now),
                )
                newly.append(achievement["codigo"])
        return newly

    def get_achievements(self) -> dict[str, Any]:
        with self._connect() as connection:
            self._sync_achievements(connection)
            unlocked = {
                row["codigo"]: row["desbloqueado_em"]
                for row in connection.execute(
                    "SELECT codigo, desbloqueado_em FROM achievements"
                ).fetchall()
            }
            items = [
                {
                    "codigo": achievement["codigo"],
                    "nome": achievement["nome"],
                    "icone": achievement["icone"],
                    "descricao": achievement["descricao"],
                    "desbloqueado": achievement["codigo"] in unlocked,
                    "desbloqueado_em": unlocked.get(achievement["codigo"]),
                }
                for achievement in ACHIEVEMENTS
            ]
            total = len(items)
            conquistadas = sum(1 for item in items if item["desbloqueado"])
            streak = self._calendar_streak(connection)
            return {
                "items": items,
                "total": total,
                "conquistadas": conquistadas,
                "percent": round((conquistadas / total) * 100) if total else 0,
                "streak": streak,
            }

    def _achievement_by_code(self, code: str) -> dict[str, Any] | None:
        for achievement in ACHIEVEMENTS:
            if achievement["codigo"] == code:
                return {
                    "codigo": achievement["codigo"],
                    "nome": achievement["nome"],
                    "icone": achievement["icone"],
                    "descricao": achievement["descricao"],
                }
        return None

    def _remaining_days(self, connection: sqlite3.Connection, plan_id: int) -> int:
        row = connection.execute(
            """
            SELECT COUNT(*) AS remaining
            FROM (
                SELECT dia
                FROM reading_progress
                WHERE plano_id = ?
                GROUP BY dia
                HAVING SUM(CASE WHEN concluido = 1 THEN 1 ELSE 0 END) < COUNT(*)
            )
            """,
            (plan_id,),
        ).fetchone()
        return int(row["remaining"] or 0)

    def _estimate_minutes(self, verses: int) -> int:
        return max(1, int(math.ceil(verses / Config.VERSES_PER_MINUTE))) if verses else 0

    def _daily_portion_date(self, day: int):
        return datetime(ANNUAL_PLAN_YEAR, 1, 1).date() + timedelta(days=day - 1)

    def _format_daily_portion_date(self, value) -> str:
        months = (
            "janeiro", "fevereiro", "março", "abril", "maio", "junho",
            "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
        )
        return f"{value.day:02d} de {months[value.month - 1]}"
