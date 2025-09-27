from flask import Flask, render_template, request, redirect, url_for, flash, session, g
from werkzeug.utils import secure_filename
from sqlalchemy import func, and_, desc
from datetime import date, datetime
import os
import pytz
from functools import wraps

from models import db, Runner, Entry, CurrentChallenge, init_db

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg"}

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "mimo"

TRANSLATIONS = {
    "fr": {
        "dashboard": {
            "page_title": "Dashboard — Défi en cours",
            "heading": "🏁 Dashboard — Défi en cours",
            "no_challenge_flash": "Aucun défi en cours. Créez-le depuis Admin → Défi.",
            "no_challenge": "Aucun défi n'est défini. Rendez-vous dans l'onglet <b>Admin → Défi</b> pour créer le défi en cours.",
            "goal_label": "🎯 Objectif",
            "remaining_label": "⏳ Il reste",
            "progress_heading": "🚀 Progression globale",
            "progress_sentence": "<b>%(total)s km parcourus</b> / %(goal)s km — <b>%(percent)s%%</b> atteints",
            "goal_reached": "🎉 Objectif atteint ! Bravo l'équipe !",
            "leaders_heading": "🏆 Classement des coureurs",
            "no_runners": "Aucun coureur n'est encore enregistré. Ajoutez des coureurs dans l'onglet <b>Admin → Coureurs</b>.",
            "table_photo": "Photo",
            "table_runner": "Coureur",
            "table_total": "Total (km)",
        }
    },
    "en": {
        "dashboard": {
            "page_title": "Dashboard — Current Challenge",
            "heading": "🏁 Dashboard — Current Challenge",
            "no_challenge_flash": "No active challenge. Create one via Admin → Challenge.",
            "no_challenge": "No challenge is defined yet. Head to <b>Admin → Challenge</b> to create one.",
            "goal_label": "🎯 Goal",
            "remaining_label": "⏳ Remaining",
            "progress_heading": "🚀 Overall Progress",
            "progress_sentence": "<b>%(total)s km completed</b> / %(goal)s km — <b>%(percent)s%%</b> achieved",
            "goal_reached": "🎉 Goal reached! Great job team!",
            "leaders_heading": "🏆 Runner Leaderboard",
            "no_runners": "No runners registered yet. Add runners via <b>Admin → Runners</b>.",
            "table_photo": "Photo",
            "table_runner": "Runner",
            "table_total": "Total (km)",
        }
    },
}

def create_app():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///running.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SECRET_KEY"] = "change-me"  # à remplacer en prod
    app.config["UPLOAD_FOLDER"] = os.path.join("static", "uploads")

    db.init_app(app)
    with app.app_context():
        init_db()

    default_locale = "fr"

    def is_admin_logged_in() -> bool:
        return bool(session.get("is_admin"))

    def admin_required(view_func):
        @wraps(view_func)
        def wrapped(*args, **kwargs):
            if not is_admin_logged_in():
                flash("Authentification administrateur requise.", "warning")
                return redirect(url_for("login", next=request.path))
            return view_func(*args, **kwargs)

        return wrapped

    @app.before_request
    def determine_locale():
        lang_param = request.args.get("lang")
        if lang_param in TRANSLATIONS:
            session["preferred_locale"] = lang_param
        preferred = session.get("preferred_locale")
        if preferred in TRANSLATIONS:
            g.locale = preferred
        else:
            g.locale = request.accept_languages.best_match(tuple(TRANSLATIONS.keys())) or default_locale

    @app.context_processor
    def inject_now():
        locale = getattr(g, "locale", default_locale)
        texts = TRANSLATIONS.get(locale, TRANSLATIONS[default_locale])
        return {
            "now": datetime.now(),
            "is_admin": is_admin_logged_in(),
            "locale": locale,
            "texts": texts,
        }

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if is_admin_logged_in():
            next_url = request.args.get("next") or url_for("dashboard")
            flash("Vous êtes déjà connecté en tant qu'admin.", "info")
            return redirect(next_url)

        next_url = request.values.get("next")
        if request.method == "POST":
            username = (request.form.get("username") or "").strip()
            password = request.form.get("password") or ""
            if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
                session["is_admin"] = True
                flash("Connexion administrateur réussie.", "success")
                return redirect(next_url or url_for("dashboard"))
            flash("Identifiants invalides.", "danger")

        return render_template("login.html", next_url=next_url)

    @app.post("/logout")
    def logout():
        session.pop("is_admin", None)
        flash("Déconnexion effectuée.", "info")
        return redirect(url_for("dashboard"))

    # ---------------- Helpers ----------------
    def allowed_file(filename: str) -> bool:
        return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

    def paris_today():
        tz = pytz.timezone("Europe/Paris")
        return datetime.now(tz).date()

    def days_left(end_d: date) -> int:
        today = paris_today()
        remaining = (end_d - today).days
        return max(0, remaining)

    def total_km_between(start_d: date, end_d: date) -> float:
        total = db.session.query(func.coalesce(func.sum(Entry.distance_km), 0.0)).filter(
            Entry.date.between(start_d, end_d)
        ).scalar() or 0.0
        return float(total)

    def format_remaining(locale: str, days: int, km: float) -> str:
        km_value = int(round(km))
        if locale == "en":
            day_word = "day" if days == 1 else "days"
        else:
            day_word = "jour" if days == 1 else "jours"
        return f"{days} {day_word} / {km_value} Km"

    # ---------------- Routes: Dashboard ----------------
    @app.route("/")
    def dashboard():
        locale = getattr(g, "locale", default_locale)
        locale_texts = TRANSLATIONS.get(locale, TRANSLATIONS[default_locale])
        dashboard_texts = locale_texts["dashboard"]
        ch = db.session.get(CurrentChallenge, 1)
        if not ch:
            flash(dashboard_texts["no_challenge_flash"], "warning")
            return render_template(
                "dashboard.html",
                challenge=None,
                total_km=0.0,
                goal_km=0.0,
                percent=0.0,
                left_days=0,
                remaining_km=0.0,
                remaining_text=format_remaining(locale, 0, 0.0),
                leaders=[],
            )

        start_d = ch.start_date
        end_d = ch.end_date
        goal_km = ch.goal_km
        total_km = total_km_between(start_d, end_d)
        percent = 0.0 if goal_km <= 0 else min(100.0, (total_km / goal_km) * 100.0)
        left = days_left(end_d)
        remaining_km = max(0.0, goal_km - total_km)
        remaining_text = format_remaining(locale, left, remaining_km)

        # Leaderboard
        q = (
            db.session.query(
                Runner.id,
                Runner.name,
                Runner.photo_path,
                func.coalesce(func.sum(Entry.distance_km), 0.0).label("total_km"),
            )
            .outerjoin(Entry, and_(Entry.runner_id == Runner.id, Entry.date.between(start_d, end_d)))
            .group_by(Runner.id, Runner.name, Runner.photo_path)
            .order_by(desc("total_km"), Runner.name.asc())
        )
        leaders = q.all()

        return render_template(
            "dashboard.html",
            challenge=ch,
            total_km=round(total_km, 2),
            goal_km=goal_km,
            percent=round(percent, 1),
            left_days=left,
            remaining_km=round(remaining_km, 2),
            remaining_text=remaining_text,
            leaders=leaders,
        )

    # ---------------- Admin: Challenge ----------------
    @app.route("/admin/challenge", methods=["GET", "POST"])
    @admin_required
    def admin_challenge():
        ch = db.session.get(CurrentChallenge, 1)
        if request.method == "POST":
            try:
                goal_km = float(request.form.get("goal_km", "0"))
                start_date_str = request.form.get("start_date", "")
                end_date_str = request.form.get("end_date", "")
                reset = request.form.get("reset") == "on"

                start_d = date.fromisoformat(start_date_str)
                end_d = date.fromisoformat(end_date_str)
                if end_d < start_d:
                    raise ValueError("La date de fin doit être postérieure ou égale à la date de début.")
                if goal_km <= 0:
                    raise ValueError("L'objectif (km) doit être supérieur à 0.")

                if ch is None:
                    ch = CurrentChallenge(id=1, goal_km=goal_km, start_date=start_d, end_date=end_d)
                    db.session.add(ch)
                else:
                    ch.goal_km = goal_km
                    ch.start_date = start_d
                    ch.end_date = end_d

                db.session.commit()

                if reset:
                    # supprimer toutes les entrées
                    Entry.query.delete()
                    db.session.commit()
                    flash("Toutes les entrées ont été supprimées. La progression est réinitialisée à 0%.", "info")

                flash("Défi enregistré avec succès.", "success")
                return redirect(url_for("admin_challenge"))
            except Exception as e:
                db.session.rollback()
                flash(f"Erreur: {e}", "danger")

        return render_template("admin_challenge.html", challenge=ch)

    # ---------------- Admin: Runners ----------------
    @app.route("/admin/runners", methods=["GET", "POST"])
    @admin_required
    def admin_runners():
        if request.method == "POST":
            try:
                name = (request.form.get("name") or "").strip()
                photo = request.files.get("photo")
                if not name:
                    raise ValueError("Le nom du coureur est obligatoire.")

                photo_path = None
                if photo and allowed_file(photo.filename):
                    filename = secure_filename(photo.filename)
                    # eviter collisions
                    ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
                    filename = f"{ts}_{filename}"
                    save_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
                    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
                    photo.save(save_path)
                    photo_path = f"uploads/{filename}"  # relatif à /static

                runner = Runner(name=name, photo_path=photo_path)
                db.session.add(runner)
                db.session.commit()
                flash("Coureur ajouté.", "success")
                return redirect(url_for("admin_runners"))
            except Exception as e:
                db.session.rollback()
                flash(f"Erreur: {e}", "danger")

        runners = Runner.query.order_by(Runner.created_at.desc()).all()
        return render_template("admin_runners.html", runners=runners)

    @app.post("/admin/runner/<int:runner_id>/update")
    @admin_required
    def update_runner_view(runner_id: int):
        runner = db.session.get(Runner, runner_id)
        if not runner:
            flash("Coureur introuvable.", "warning")
            return redirect(url_for("admin_runners"))
        try:
            name = (request.form.get("name") or "").strip()
            photo = request.files.get("photo")
            if not name:
                raise ValueError("Le nom du coureur est obligatoire.")
            runner.name = name

            if photo and allowed_file(photo.filename):
                filename = secure_filename(photo.filename)
                ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
                filename = f"{ts}_{filename}"
                save_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
                os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
                photo.save(save_path)
                runner.photo_path = f"uploads/{filename}"

            db.session.commit()
            flash("Coureur mis à jour.", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"Erreur: {e}", "danger")
        return redirect(url_for("admin_runners"))

    @app.post("/admin/runner/<int:runner_id>/delete")
    @admin_required
    def delete_runner_view(runner_id: int):
        runner = db.session.get(Runner, runner_id)
        if not runner:
            flash("Coureur introuvable.", "warning")
            return redirect(url_for("admin_runners"))
        try:
            db.session.delete(runner)  # ON DELETE CASCADE pour entries si configuré
            db.session.commit()
            flash("Coureur supprimé.", "warning")
        except Exception as e:
            db.session.rollback()
            flash(f"Erreur: {e}", "danger")
        return redirect(url_for("admin_runners"))

    # ---------------- Admin: Entries ----------------
    @app.route("/admin/entries", methods=["GET", "POST"])
    @admin_required
    def admin_entries():
        ch = db.session.get(CurrentChallenge, 1)
        runners = Runner.query.order_by(Runner.name.asc()).all()

        if request.method == "POST":
            try:
                if not ch:
                    raise ValueError("Créez d'abord le défi en cours.")
                runner_id = int(request.form.get("runner_id"))
                date_str = request.form.get("date")
                distance_km = float(request.form.get("distance_km"))
                if distance_km <= 0:
                    raise ValueError("La distance doit être > 0.")
                d = date.fromisoformat(date_str)
                if d < ch.start_date or d > ch.end_date:
                    raise ValueError(f"La date doit être entre {ch.start_date} et {ch.end_date}.")
                runner = db.session.get(Runner, runner_id)
                if not runner:
                    raise ValueError("Le coureur sélectionné n'existe pas.")

                e = Entry(runner_id=runner_id, date=d, distance_km=distance_km)
                db.session.add(e)
                db.session.commit()
                flash("Entrée ajoutée.", "success")
                return redirect(url_for("admin_entries"))
            except Exception as e:
                db.session.rollback()
                flash(f"Erreur: {e}", "danger")

        # List entries (limit)
        entries = (
            db.session.query(Entry, Runner.name.label("runner_name"))
            .join(Runner, Runner.id == Entry.runner_id)
            .order_by(Entry.date.desc(), Entry.id.desc())
            .limit(300)
            .all()
        )
        return render_template("admin_entries.html", challenge=ch, runners=runners, entries=entries)

    @app.post("/admin/entry/<int:entry_id>/update")
    @admin_required
    def update_entry_view(entry_id: int):
        ch = db.session.get(CurrentChallenge, 1)
        e = db.session.get(Entry, entry_id)
        if not e:
            flash("Entrée introuvable.", "warning")
            return redirect(url_for("admin_entries"))
        try:
            runner_id = int(request.form.get("runner_id"))
            date_str = request.form.get("date")
            distance_km = float(request.form.get("distance_km"))
            if distance_km <= 0:
                raise ValueError("La distance doit être > 0.")
            d = date.fromisoformat(date_str)
            if ch and (d < ch.start_date or d > ch.end_date):
                raise ValueError(f"La date doit être entre {ch.start_date} et {ch.end_date}.")
            if not db.session.get(Runner, runner_id):
                raise ValueError("Le coureur sélectionné n'existe pas.")
            e.runner_id = runner_id
            e.date = d
            e.distance_km = distance_km
            e.updated_at = datetime.utcnow()
            db.session.commit()
            flash("Entrée mise à jour.", "success")
        except Exception as ex:
            db.session.rollback()
            flash(f"Erreur: {ex}", "danger")
        return redirect(url_for("admin_entries"))

    @app.post("/admin/entry/<int:entry_id>/delete")
    @admin_required
    def delete_entry_view(entry_id: int):
        e = db.session.get(Entry, entry_id)
        if not e:
            flash("Entrée introuvable.", "warning")
            return redirect(url_for("admin_entries"))
        try:
            db.session.delete(e)
            db.session.commit()
            flash("Entrée supprimée.", "warning")
        except Exception as ex:
            db.session.rollback()
            flash(f"Erreur: {ex}", "danger")
        return redirect(url_for("admin_entries"))

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
