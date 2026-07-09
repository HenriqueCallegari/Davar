from __future__ import annotations

import math
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

from app.config import Config

DATABASE_PATH = Config.DATABASE_PATH
ANNUAL_PLAN_YEAR = Config.ANNUAL_PLAN_YEAR

# Conquistas: cada uma tem um predicado sobre o contexto agregado de leitura.
# O contexto expoe: total_chapters, best_streak, current_streak, completed_plans.
ACHIEVEMENTS = (
    {"codigo": "primeiro_capitulo", "nome": "Primeiro Passo", "icone": "🌱",
     "descricao": "Leia seu primeiro capitulo",
     "meta": lambda c: c["total_chapters"] >= 1},
    {"codigo": "dez_capitulos", "nome": "Aquecendo", "icone": "📗",
     "descricao": "Leia 10 capitulos",
     "meta": lambda c: c["total_chapters"] >= 10},
    {"codigo": "cinquenta_capitulos", "nome": "Constante", "icone": "📘",
     "descricao": "Leia 50 capitulos",
     "meta": lambda c: c["total_chapters"] >= 50},
    {"codigo": "cem_capitulos", "nome": "Centenario", "icone": "📚",
     "descricao": "Leia 100 capitulos",
     "meta": lambda c: c["total_chapters"] >= 100},
    {"codigo": "streak_3", "nome": "Pegando o Ritmo", "icone": "🔥",
     "descricao": "Leia em 3 dias seguidos",
     "meta": lambda c: c["best_streak"] >= 3},
    {"codigo": "streak_7", "nome": "Semana de Fogo", "icone": "🔥",
     "descricao": "Leia em 7 dias seguidos",
     "meta": lambda c: c["best_streak"] >= 7},
    {"codigo": "streak_30", "nome": "Disciplina de Ferro", "icone": "⚡",
     "descricao": "Leia em 30 dias seguidos",
     "meta": lambda c: c["best_streak"] >= 30},
    {"codigo": "nt_completo", "nome": "Novo Testamento", "icone": "✝️",
     "descricao": "Conclua o plano do Novo Testamento",
     "meta": lambda c: "novo_testamento" in c["completed_plans"]},
    {"codigo": "at_completo", "nome": "Antigo Testamento", "icone": "📜",
     "descricao": "Conclua o plano do Antigo Testamento",
     "meta": lambda c: "antigo_testamento" in c["completed_plans"]},
    {"codigo": "biblia_ano", "nome": "Biblia em um Ano", "icone": "👑",
     "descricao": "Conclua a Porcao Diaria",
     "meta": lambda c: "porcao_diaria" in c["completed_plans"]},
)


class ReadingPlanRepository:
    """SQLite access layer for reading plans, progress, notes, and statistics."""

    def __init__(self, bible: list[dict[str, Any]], db_path: Path = DATABASE_PATH) -> None:
        self.bible = bible
        self.db_path = Path(db_path)
        self.old_testament = self._flatten_books(bible[:39], "Antigo Testamento")
        self.new_testament = self._flatten_books(bible[39:], "Novo Testamento")
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

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
            """
        )

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
            connection.execute(
                """
                INSERT INTO reading_plans (id, nome, tipo, total_dias)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    nome = excluded.nome,
                    tipo = excluded.tipo,
                    total_dias = excluded.total_dias
                """,
                (plan["id"], plan["nome"], plan["tipo"], total_days),
            )

            current = connection.execute(
                """
                SELECT rp.total_dias, COUNT(rg.id) AS progress_count
                FROM reading_plans rp
                LEFT JOIN reading_progress rg ON rg.plano_id = rp.id
                WHERE rp.id = ?
                GROUP BY rp.id
                """,
                (plan["id"],),
            ).fetchone()
            needs_rebuild = (
                current is None
                or current["total_dias"] != total_days
                or current["progress_count"] != expected_count
            )

            if needs_rebuild:
                connection.execute("DELETE FROM reading_progress WHERE plano_id = ?", (plan["id"],))
                connection.execute("DELETE FROM reading_notes WHERE plano_id = ?", (plan["id"],))
                self._insert_schedule(connection, plan["id"], schedule)

            connection.execute(
                "INSERT OR IGNORE INTO user_statistics (plano_id) VALUES (?)",
                (plan["id"],),
            )
            self._refresh_statistics(connection, plan["id"])

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
            return [self._plan_summary(connection, row) for row in plans]

    def reading_overview(self) -> dict[str, Any]:
        """Agregados para o dashboard: totais, sequencia e sugestao de continuacao."""
        plans = self.list_plans()
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    SUM(CASE WHEN concluido = 1 THEN 1 ELSE 0 END) AS capitulos,
                    SUM(CASE WHEN concluido = 1 THEN versiculos ELSE 0 END) AS versiculos
                FROM reading_progress
                """
            ).fetchone()
            streak = self._calendar_streak(connection)

        chapters = int((row["capitulos"] if row else 0) or 0)
        verses = int((row["versiculos"] if row else 0) or 0)

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
            rows = connection.execute(
                """
                SELECT substr(data_conclusao, 1, 10) AS dia, COUNT(*) AS total
                FROM reading_progress
                WHERE concluido = 1 AND data_conclusao IS NOT NULL
                GROUP BY dia
                """
            ).fetchall()
            streak = self._calendar_streak(connection)

        daily_counts = {row["dia"]: int(row["total"]) for row in rows if row["dia"]}
        today = datetime.now().date()

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

            selected_day = day or self._current_day(connection, plan_id, plan["total_dias"])
            selected_day = max(1, min(int(selected_day), plan["total_dias"]))
            chapters = self._chapters_for_day(connection, plan_id, selected_day)
            note = connection.execute(
                "SELECT texto FROM reading_notes WHERE plano_id = ? AND dia = ?",
                (plan_id, selected_day),
            ).fetchone()
            statistics = self._statistics(connection, plan_id)
            day_verses = sum(chapter["versiculos"] for chapter in chapters)
            day_completed = bool(chapters) and all(chapter["concluido"] for chapter in chapters)
            first_pending = next((chapter for chapter in chapters if not chapter["concluido"]), None)
            is_daily_portion = plan["tipo"] == "porcao_diaria"
            calendar_date = self._daily_portion_date(selected_day) if is_daily_portion else None
            has_new_testament = any(chapter["testamento"] == "Novo Testamento" for chapter in chapters)

            return {
                "plan": dict(plan),
                "day": selected_day,
                "current_day": self._current_day(connection, plan_id, plan["total_dias"]),
                "chapters": chapters,
                "calendar_label": self._format_daily_portion_date(calendar_date) if calendar_date else "",
                "has_free_main_reading": is_daily_portion and not has_new_testament,
                "note": note["texto"] if note else "",
                "statistics": statistics,
                "day_completed": day_completed,
                "first_pending": first_pending,
                "estimated_minutes": self._estimate_minutes(day_verses),
                "progress": self._plan_progress(connection, plan_id),
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

            completed_at = datetime.now().isoformat(timespec="seconds") if completed else None
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
        now = datetime.now().isoformat(timespec="seconds")
        with self._connect() as connection:
            exists = connection.execute(
                "SELECT 1 FROM reading_plans WHERE id = ?",
                (plan_id,),
            ).fetchone()
            if exists is None:
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
                "current_day": self._current_day(connection, plan_id, plan["total_dias"]),
            }

    def _plan_summary(self, connection: sqlite3.Connection, plan: sqlite3.Row) -> dict[str, Any]:
        progress = self._plan_progress(connection, plan["id"])
        statistics = self._statistics(connection, plan["id"])
        return {
            **dict(plan),
            "progress": progress,
            "statistics": statistics,
            "current_day": self._current_day(connection, plan["id"], plan["total_dias"]),
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

    def _statistics(self, connection: sqlite3.Connection, plan_id: int) -> dict[str, Any]:
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

        progress = self._plan_progress(connection, plan_id)
        remaining_days = self._remaining_days(connection, plan_id)
        completion_date = datetime.now().date() + timedelta(days=max(remaining_days - 1, 0))
        calendar_streak = self._calendar_streak(connection)
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
        now = datetime.now().isoformat(timespec="seconds")
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
            (datetime.now().isoformat(timespec="seconds"), plan_id),
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

    def _record_activity(self, connection: sqlite3.Connection) -> None:
        today = datetime.now().date().isoformat()
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

        today = datetime.now().date()
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
        totals = connection.execute(
            """
            SELECT
                SUM(CASE WHEN concluido = 1 THEN 1 ELSE 0 END) AS total_chapters
            FROM reading_progress
            """
        ).fetchone()
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
            "total_chapters": int((totals["total_chapters"] if totals else 0) or 0),
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
        now = datetime.now().isoformat(timespec="seconds")
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
        return max(1, int(math.ceil(verses / 4.8))) if verses else 0

    def _daily_portion_date(self, day: int):
        return datetime(ANNUAL_PLAN_YEAR, 1, 1).date() + timedelta(days=day - 1)

    def _format_daily_portion_date(self, value) -> str:
        months = (
            "janeiro", "fevereiro", "março", "abril", "maio", "junho",
            "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
        )
        return f"{value.day:02d} de {months[value.month - 1]}"
