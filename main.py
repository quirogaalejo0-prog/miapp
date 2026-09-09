import os
import sqlite3
from kivymd.app import MDApp
from kivymd.uix.screen import MDScreen
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.gridlayout import MDGridLayout
from kivymd.uix.scrollview import MDScrollView
from kivymd.uix.list import (
    MDList,
    MDListItem,
    MDListItemLeadingIcon,
    MDListItemHeadlineText,
    MDListItemSupportingText,
)
from kivymd.uix.button import MDButton, MDButtonText, MDIconButton
from kivymd.uix.textfield import MDTextField
from kivymd.uix.dialog import (
    MDDialog,
    MDDialogHeadlineText,
    MDDialogContentContainer,
    MDDialogButtonContainer,
)
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel
from kivymd.uix.selectioncontrol import MDCheckbox
from kivymd.uix.menu import MDDropdownMenu
from kivymd.uix.fitimage import FitImage  # <-- Para mostrar el logo en miniatura
from kivy.metrics import dp

# Intentamos importar filechooser de plyer para abrir la galería/explorador de archivos
try:
    from plyer import filechooser

    has_filechooser = True
except ImportError:
    has_filechooser = False

DB_NAME = "food_trucks.db"


def obtener_ruta_db() -> str:
    """Ruta segura para Android (almacenamiento interno de la app) y para PC."""
    try:
        from android.permissions import request_permissions, Permission
        request_permissions([Permission.WRITE_EXTERNAL_STORAGE, Permission.READ_EXTERNAL_STORAGE])
    except ImportError:
        pass

    app = MDApp.get_running_app()
    base_dir = app.user_data_dir if app else os.getcwd()
    return os.path.join(base_dir, DB_NAME)


def init_db(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS food_trucks
                   (
                       id
                       INTEGER
                       PRIMARY
                       KEY
                       AUTOINCREMENT,
                       nombre
                       TEXT
                       NOT
                       NULL,
                       patente
                       TEXT,
                       logo
                       TEXT
                   )
                   """)

    # Compatibilidad por si la tabla ya existía sin la columna 'logo'
    cursor.execute("PRAGMA table_info(food_trucks)")
    columnas = [col[1] for col in cursor.fetchall()]
    if "logo" not in columnas:
        cursor.execute("ALTER TABLE food_trucks ADD COLUMN logo TEXT")

    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS stock
                   (
                       id
                       INTEGER
                       PRIMARY
                       KEY
                       AUTOINCREMENT,
                       truck_id
                       INTEGER,
                       item
                       TEXT
                       NOT
                       NULL,
                       cantidad
                       REAL
                       NOT
                       NULL,
                       unidad
                       TEXT
                       NOT
                       NULL,
                       minimo
                       REAL
                       NOT
                       NULL,
                       FOREIGN
                       KEY
                   (
                       truck_id
                   ) REFERENCES food_trucks
                   (
                       id
                   )
                       )
                   """)

    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS agenda
                   (
                       id
                       INTEGER
                       PRIMARY
                       KEY
                       AUTOINCREMENT,
                       truck_id
                       INTEGER,
                       titulo
                       TEXT
                       NOT
                       NULL,
                       fecha
                       TEXT
                       NOT
                       NULL,
                       categoria
                       TEXT
                       DEFAULT
                       'Evento / Fecha',
                       FOREIGN
                       KEY
                   (
                       truck_id
                   ) REFERENCES food_trucks
                   (
                       id
                   )
                       )
                   """)

    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS agenda_items
                   (
                       id
                       INTEGER
                       PRIMARY
                       KEY
                       AUTOINCREMENT,
                       agenda_id
                       INTEGER,
                       item
                       TEXT
                       NOT
                       NULL,
                       completado
                       INTEGER
                       DEFAULT
                       0,
                       FOREIGN
                       KEY
                   (
                       agenda_id
                   ) REFERENCES agenda
                   (
                       id
                   ) ON DELETE CASCADE
                       )
                   """)

    cursor.execute("SELECT COUNT(*) FROM food_trucks")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO food_trucks (nombre, patente, logo) VALUES ('Tráiler Principal', 'AB123CD', '')")
        cursor.execute(
            "INSERT INTO stock (truck_id, item, cantidad, unidad, minimo) VALUES (1, 'Garrafa de Gas 45kg', 1, 'Unidades', 2)")
        cursor.execute(
            "INSERT INTO stock (truck_id, item, cantidad, unidad, minimo) VALUES (1, 'Bolsas de Papa', 15, 'Bolsas', 5)")
        cursor.execute(
            "INSERT INTO agenda (truck_id, titulo, fecha, categoria) VALUES (1, 'Evento Colectividades', '2026-10-15', 'Evento / Fecha')")
        cursor.execute(
            "INSERT INTO agenda (truck_id, titulo, fecha, categoria) VALUES (1, 'Renovar Permiso Municipal', '2026-11-01', 'Permisos y Habilitaciones')")
        cursor.execute("INSERT INTO agenda_items (agenda_id, item, completado) VALUES (1, '3 Garrafas de Gas', 1)")
        cursor.execute(
            "INSERT INTO agenda_items (agenda_id, item, completado) VALUES (1, '20 Bolsas de Papa Pelada/Bastón', 0)")

    conn.commit()
    conn.close()


class FoodTruckApp(MDApp):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.dialog = None
        self.current_truck_id = None
        self.menu_trucks = None
        self.db_path = ""
        self.btn_sec_stock = None
        self.btn_sec_agenda = None
        self.img_logo_header = None  # Referencia al icono/logo de la cabecera

    def build(self):
        self.theme_cls.theme_style = "Light"
        self.theme_cls.primary_palette = "Indigo"

        self.db_path = obtener_ruta_db()
        init_db(self.db_path)

        root = MDBoxLayout(
            orientation="vertical",
            padding=dp(16),
            spacing=dp(16),
            md_bg_color=[0.94, 0.95, 0.97, 1]
        )

        # --- SECTOR CABECERA: SELECCIÓN DE TRÁILER Y LOGO ---
        header_card = MDCard(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(64),
            padding=dp(8),
            spacing=dp(10),
            style="elevated"
        )

        # Contenedor para la miniatura del logo o ícono en la cabecera
        self.box_logo_preview = MDBoxLayout(
            size_hint=(None, None),
            size=(dp(48), dp(48)),
            radius=[dp(24)]
        )
        self.img_logo_header = MDIconButton(icon="truck-fast-outline", disabled=True)
        self.box_logo_preview.add_widget(self.img_logo_header)

        self.btn_select_truck = MDButton(
            MDButtonText(text="Cargando Tráilers..."),
            style="filled",
            size_hint_x=0.65,
            on_release=self.abrir_menu_trucks
        )
        btn_edit_truck = MDIconButton(icon="pencil-box-outline", on_release=self.modal_editar_truck)
        btn_add_truck = MDIconButton(icon="plus-box-outline", on_release=self.modal_agregar_truck)

        header_card.add_widget(self.box_logo_preview)
        header_card.add_widget(self.btn_select_truck)
        header_card.add_widget(btn_edit_truck)
        header_card.add_widget(btn_add_truck)
        root.add_widget(header_card)

        # --- NAVEGACIÓN DE SECCIONES (FIJA ARRIBA) ---
        nav_box = MDBoxLayout(orientation="horizontal", size_hint_y=None, height=dp(48), spacing=dp(12))

        self.btn_sec_stock = MDButton(
            MDButtonText(text="Stock e Inventario"),
            style="filled",
            size_hint_x=0.5,
            on_release=lambda x: self.cambiar_seccion("stock")
        )
        self.btn_sec_agenda = MDButton(
            MDButtonText(text="Agenda y Permisos"),
            style="outlined",
            size_hint_x=0.5,
            on_release=lambda x: self.cambiar_seccion("agenda")
        )

        nav_box.add_widget(self.btn_sec_stock)
        nav_box.add_widget(self.btn_sec_agenda)
        root.add_widget(nav_box)

        # --- CONTENEDOR CON SCROLL PARA EL CONTENIDO VARIABLE ---
        main_scroll = MDScrollView()

        content_root = MDBoxLayout(
            orientation="vertical",
            spacing=dp(16),
            size_hint_y=None
        )
        content_root.bind(minimum_height=content_root.setter('height'))

        self.container_stock = MDBoxLayout(orientation="vertical", spacing=dp(12), size_hint_y=None)
        self.container_stock.bind(minimum_height=self.container_stock.setter('height'))

        self.container_agenda = MDBoxLayout(orientation="vertical", spacing=dp(12), size_hint_y=None)
        self.container_agenda.bind(minimum_height=self.container_agenda.setter('height'))
        self.container_agenda.height = 0
        self.container_agenda.opacity = 0

        # --- PESTAÑA STOCK ---
        card_form_stock = MDCard(
            orientation="vertical",
            size_hint_y=None,
            height=dp(310),
            padding=dp(16),
            spacing=dp(12),
            style="outlined"
        )
        lbl_stock_title = MDLabel(text="Registrar Nuevo Insumo", bold=True, size_hint_y=None, height=dp(24))

        form_stock = MDGridLayout(cols=2, spacing=dp(12), size_hint_y=None, height=dp(170))

        box_s1 = MDBoxLayout(orientation="vertical", spacing=dp(4))
        box_s1.add_widget(
            MDLabel(text="Insumo / Ítem:", font_style="Body", role="medium", size_hint_y=None, height=dp(20)))
        self.tf_s_item = MDTextField(hint_text="Ej: Bolsas de Papa")
        box_s1.add_widget(self.tf_s_item)

        box_s2 = MDBoxLayout(orientation="vertical", spacing=dp(4))
        box_s2.add_widget(MDLabel(text="Cantidad:", font_style="Body", role="medium", size_hint_y=None, height=dp(20)))
        self.tf_s_cant = MDTextField(hint_text="Ej: 15", input_filter="float")
        box_s2.add_widget(self.tf_s_cant)

        box_s3 = MDBoxLayout(orientation="vertical", spacing=dp(4))
        box_s3.add_widget(MDLabel(text="Unidad:", font_style="Body", role="medium", size_hint_y=None, height=dp(20)))
        self.tf_s_uni = MDTextField(hint_text="Ej: kg, un, bolsas")
        box_s3.add_widget(self.tf_s_uni)

        box_s4 = MDBoxLayout(orientation="vertical", spacing=dp(4))
        box_s4.add_widget(
            MDLabel(text="Stock Mínimo Alerta:", font_style="Body", role="medium", size_hint_y=None, height=dp(20)))
        self.tf_s_min = MDTextField(hint_text="Ej: 5", input_filter="float")
        box_s4.add_widget(self.tf_s_min)

        form_stock.add_widget(box_s1)
        form_stock.add_widget(box_s2)
        form_stock.add_widget(box_s3)
        form_stock.add_widget(box_s4)

        btn_add_stock = MDButton(
            MDButtonText(text="Agregar al Inventario"),
            style="filled",
            size_hint_y=None,
            height=dp(42),
            on_release=self.agregar_stock
        )

        card_form_stock.add_widget(lbl_stock_title)
        card_form_stock.add_widget(form_stock)
        card_form_stock.add_widget(btn_add_stock)

        self.list_stock = MDList(size_hint_y=None)
        self.list_stock.bind(minimum_height=self.list_stock.setter('height'))

        self.container_stock.add_widget(card_form_stock)
        self.container_stock.add_widget(self.list_stock)

        # --- PESTAÑA AGENDA ---
        card_form_agenda = MDCard(
            orientation="vertical",
            size_hint_y=None,
            height=dp(385),
            padding=dp(16),
            spacing=dp(12),
            style="outlined"
        )
        lbl_agenda_title = MDLabel(text="Nuevo Evento o Trámite", bold=True, size_hint_y=None, height=dp(24))

        form_agenda = MDBoxLayout(orientation="vertical", spacing=dp(10), size_hint_y=None, height=dp(245))

        box_a1 = MDBoxLayout(orientation="vertical", spacing=dp(4), size_hint_y=None, height=dp(75))
        box_a1.add_widget(
            MDLabel(text="Título del Evento / Trámite:", font_style="Body", role="medium", size_hint_y=None,
                    height=dp(20)))
        self.tf_a_titulo = MDTextField(hint_text="Ej: Habilitación Municipal")
        box_a1.add_widget(self.tf_a_titulo)

        box_a2 = MDBoxLayout(orientation="vertical", spacing=dp(4), size_hint_y=None, height=dp(75))
        box_a2.add_widget(
            MDLabel(text="Fecha (AAAA-MM-DD):", font_style="Body", role="medium", size_hint_y=None, height=dp(20)))
        self.tf_a_fecha = MDTextField(hint_text="Ej: 2026-11-01")
        box_a2.add_widget(self.tf_a_fecha)

        box_a3 = MDBoxLayout(orientation="vertical", spacing=dp(4), size_hint_y=None, height=dp(75))
        box_a3.add_widget(MDLabel(text="Categoría:", font_style="Body", role="medium", size_hint_y=None, height=dp(20)))
        self.tf_a_cat = MDTextField(hint_text="Ej: Permisos / Evento")
        box_a3.add_widget(self.tf_a_cat)

        form_agenda.add_widget(box_a1)
        form_agenda.add_widget(box_a2)
        form_agenda.add_widget(box_a3)

        btn_add_agenda = MDButton(
            MDButtonText(text="Guardar en Agenda"),
            style="filled",
            size_hint_y=None,
            height=dp(42),
            on_release=self.agregar_agenda
        )

        card_form_agenda.add_widget(lbl_agenda_title)
        card_form_agenda.add_widget(form_agenda)
        card_form_agenda.add_widget(btn_add_agenda)

        self.list_agenda = MDList(size_hint_y=None)
        self.list_agenda.bind(minimum_height=self.list_agenda.setter('height'))

        self.container_agenda.add_widget(card_form_agenda)
        self.container_agenda.add_widget(self.list_agenda)

        content_root.add_widget(self.container_stock)
        content_root.add_widget(self.container_agenda)

        main_scroll.add_widget(content_root)
        root.add_widget(main_scroll)

        self.cargar_trucks()
        return root

    def cambiar_seccion(self, seccion):
        if seccion == "stock":
            self.btn_sec_stock.style = "filled"
            self.btn_sec_stock.md_bg_color = self.theme_cls.primaryColor

            self.btn_sec_agenda.style = "outlined"
            self.btn_sec_agenda.md_bg_color = [0, 0, 0, 0]

            self.container_stock.height = self.container_stock.minimum_height
            self.container_stock.opacity = 1
            self.container_agenda.height = 0
            self.container_agenda.opacity = 0
        else:
            self.btn_sec_stock.style = "outlined"
            self.btn_sec_stock.md_bg_color = [0, 0, 0, 0]

            self.btn_sec_agenda.style = "filled"
            self.btn_sec_agenda.md_bg_color = self.theme_cls.primaryColor

            self.container_stock.height = 0
            self.container_stock.opacity = 0
            self.container_agenda.height = self.container_agenda.minimum_height
            self.container_agenda.opacity = 1

    def cargar_trucks(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT id, nombre, patente, logo FROM food_trucks")
        trucks = cursor.fetchall()
        conn.close()

        if trucks:
            if not self.current_truck_id:
                self.current_truck_id = trucks[0][0]

            # Buscamos los datos del truck actual seleccionado
            current_truck = next((t for t in trucks if t[0] == self.current_truck_id), trucks[0])
            self.btn_select_truck.children[0].text = f"{current_truck[1]} ({current_truck[2] or 'Sin patente'})"

            # Actualizamos la visualización del logo en la cabecera
            self.actualizar_logo_header(current_truck[3])

            menu_items = [
                {
                    "text": f"{t[1]} ({t[2] or 'Sin patente'})",
                    "on_release": lambda x=t: self.seleccionar_truck(x[0], f"{x[1]} ({x[2] or 'Sin patente'})", x[3]),
                } for t in trucks
            ]
            self.menu_trucks = MDDropdownMenu(
                caller=self.btn_select_truck,
                items=menu_items,
                width_mult=4,
            )

        self.cargar_stock()
        self.cargar_agenda()

    def actualizar_logo_header(self, logo_path):
        self.box_logo_preview.clear_widgets()
        if logo_path and os.path.exists(logo_path):
            img = FitImage(source=logo_path, radius=[dp(24)])
            self.box_logo_preview.add_widget(img)
        else:
            ico = MDIconButton(icon="truck-fast-outline", disabled=True)
            self.box_logo_preview.add_widget(ico)

    def abrir_menu_trucks(self, instance):
        if self.menu_trucks:
            self.menu_trucks.open()

    def seleccionar_truck(self, truck_id, nombre, logo_path):
        self.current_truck_id = truck_id
        self.btn_select_truck.children[0].text = nombre
        self.actualizar_logo_header(logo_path)
        if self.menu_trucks:
            self.menu_trucks.dismiss()
        self.cargar_stock()
        self.cargar_agenda()

    def cargar_stock(self):
        self.list_stock.clear_widgets()
        if not self.current_truck_id:
            return

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT id, item, cantidad, unidad, minimo FROM stock WHERE truck_id = ?",
                       (self.current_truck_id,))
        filas = cursor.fetchall()
        conn.close()

        for s_id, item, cant, uni, minimo in filas:
            alerta = cant <= minimo
            icono = "alert-circle-outline" if alerta else "package-variant"

            item_widget = MDListItem()
            item_widget.add_widget(MDListItemLeadingIcon(icon=icono))
            item_widget.add_widget(MDListItemHeadlineText(text=f"{item} — {cant} {uni}"))
            item_widget.add_widget(MDListItemSupportingText(text=f"Stock mínimo requerido: {minimo} {uni}"))

            box_actions = MDBoxLayout(orientation="horizontal", size_hint_x=None, width=dp(96), spacing=dp(4))

            btn_editar = MDIconButton(
                icon="pencil-outline",
                on_release=lambda x, id_s=s_id: self.modal_editar_stock(id_s)
            )
            btn_eliminar = MDIconButton(
                icon="delete-outline",
                on_release=lambda x, id_s=s_id: self.eliminar_stock(id_s)
            )

            box_actions.add_widget(btn_editar)
            box_actions.add_widget(btn_eliminar)
            item_widget.add_widget(box_actions)

            self.list_stock.add_widget(item_widget)

        self.container_stock.height = self.container_stock.minimum_height

    def agregar_stock(self, instance):
        if self.tf_s_item.text and self.tf_s_cant.text and self.current_truck_id:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO stock (truck_id, item, cantidad, unidad, minimo) VALUES (?, ?, ?, ?, ?)",
                (self.current_truck_id, self.tf_s_item.text, float(self.tf_s_cant.text), self.tf_s_uni.text or "un",
                 float(self.tf_s_min.text or 1))
            )
            conn.commit()
            conn.close()

            self.tf_s_item.text = ""
            self.tf_s_cant.text = ""
            self.tf_s_uni.text = ""
            self.tf_s_min.text = ""
            self.cargar_stock()

    def modal_editar_stock(self, stock_id):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT item, cantidad, unidad, minimo FROM stock WHERE id = ?", (stock_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return

        tf_item = MDTextField(text=row[0], hint_text="Insumo / Ítem")
        tf_cant = MDTextField(text=str(row[1]), hint_text="Cantidad", input_filter="float")
        tf_uni = MDTextField(text=row[2], hint_text="Unidad")
        tf_min = MDTextField(text=str(row[3]), hint_text="Stock Mínimo Alerta", input_filter="float")

        content = MDBoxLayout(orientation="vertical", spacing=dp(12), size_hint_y=None, height=dp(250))
        content.add_widget(tf_item)
        content.add_widget(tf_cant)
        content.add_widget(tf_uni)
        content.add_widget(tf_min)

        def actualizar_stock(x):
            if tf_item.text and tf_cant.text:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE stock SET item = ?, cantidad = ?, unidad = ?, minimo = ? WHERE id = ?",
                    (tf_item.text, float(tf_cant.text), tf_uni.text or "un", float(tf_min.text or 1), stock_id)
                )
                conn.commit()
                conn.close()
                self.dialog.dismiss()
                self.cargar_stock()

        self.dialog = MDDialog(
            MDDialogHeadlineText(text="Editar Insumo de Stock"),
            MDDialogContentContainer(
                content,
                orientation="vertical",
            ),
            MDDialogButtonContainer(
                MDButton(MDButtonText(text="Cancelar"), style="text", on_release=lambda x: self.dialog.dismiss()),
                MDButton(MDButtonText(text="Guardar Cambios"), style="filled", on_release=actualizar_stock),
                spacing=dp(8),
            )
        )
        self.dialog.open()

    def eliminar_stock(self, stock_id):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM stock WHERE id = ?", (stock_id,))
        conn.commit()
        conn.close()
        self.cargar_stock()

    def cargar_agenda(self):
        self.list_agenda.clear_widgets()
        if not self.current_truck_id:
            return

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT id, titulo, fecha, categoria FROM agenda WHERE truck_id = ? ORDER BY fecha ASC",
                       (self.current_truck_id,))
        eventos = cursor.fetchall()

        for e_id, titulo, fecha, categoria in eventos:
            card = MDCard(
                orientation="vertical",
                size_hint_y=None,
                height=dp(115),
                padding=dp(12),
                spacing=dp(6),
                style="elevated"
            )

            lbl_title = MDLabel(text=f"{titulo} [{categoria or 'General'}]", bold=True, size_hint_y=None, height=dp(24))
            lbl_fecha = MDLabel(text=f"Fecha: {fecha}", theme_text_color="Secondary", size_hint_y=None, height=dp(20))

            box_actions = MDBoxLayout(orientation="horizontal", size_hint_y=None, height=dp(36), spacing=dp(4))

            btn_subitems = MDButton(
                MDButtonText(text="Tareas"),
                style="text",
                size_hint_x=0.5,
                on_release=lambda x, ev_id=e_id, t_ev=titulo: self.modal_checklist(ev_id, t_ev)
            )

            box_edit_del = MDBoxLayout(orientation="horizontal", size_hint_x=0.5, spacing=dp(2))
            btn_editar_ev = MDIconButton(
                icon="pencil-outline",
                on_release=lambda x, ev_id=e_id: self.modal_editar_agenda(ev_id)
            )
            btn_del_ev = MDIconButton(
                icon="delete-outline",
                on_release=lambda x, ev_id=e_id: self.eliminar_evento(ev_id)
            )

            box_edit_del.add_widget(btn_editar_ev)
            box_edit_del.add_widget(btn_del_ev)

            box_actions.add_widget(btn_subitems)
            box_actions.add_widget(box_edit_del)

            card.add_widget(lbl_title)
            card.add_widget(lbl_fecha)
            card.add_widget(box_actions)

            self.list_agenda.add_widget(card)

        conn.close()
        self.container_agenda.height = self.container_agenda.minimum_height

    def agregar_agenda(self, instance):
        if self.tf_a_titulo.text and self.tf_a_fecha.text and self.current_truck_id:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO agenda (truck_id, titulo, fecha, categoria) VALUES (?, ?, ?, ?)",
                (self.current_truck_id, self.tf_a_titulo.text, self.tf_a_fecha.text,
                 self.tf_a_cat.text or "Evento / Fecha")
            )
            conn.commit()
            conn.close()

            self.tf_a_titulo.text = ""
            self.tf_a_fecha.text = ""
            self.tf_a_cat.text = ""
            self.cargar_agenda()

    def modal_editar_agenda(self, agenda_id):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT titulo, fecha, categoria FROM agenda WHERE id = ?", (agenda_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return

        content = MDBoxLayout(orientation="vertical", spacing=dp(10), size_hint_y=None, height=dp(245))

        box_1 = MDBoxLayout(orientation="vertical", spacing=dp(4), size_hint_y=None, height=dp(75))
        box_1.add_widget(
            MDLabel(text="Título del Evento / Trámite:", font_style="Body", role="medium", size_hint_y=None,
                    height=dp(20)))
        tf_titulo = MDTextField(text=row[0], hint_text="Ej: Habilitación Municipal")
        box_1.add_widget(tf_titulo)

        box_2 = MDBoxLayout(orientation="vertical", spacing=dp(4), size_hint_y=None, height=dp(75))
        box_2.add_widget(
            MDLabel(text="Fecha (AAAA-MM-DD):", font_style="Body", role="medium", size_hint_y=None, height=dp(20)))
        tf_fecha = MDTextField(text=row[1], hint_text="Ej: 2026-11-01")
        box_2.add_widget(tf_fecha)

        box_3 = MDBoxLayout(orientation="vertical", spacing=dp(4), size_hint_y=None, height=dp(75))
        box_3.add_widget(MDLabel(text="Categoría:", font_style="Body", role="medium", size_hint_y=None, height=dp(20)))
        tf_cat = MDTextField(text=row[2] or "", hint_text="Ej: Permisos / Evento")
        box_3.add_widget(tf_cat)

        content.add_widget(box_1)
        content.add_widget(box_2)
        content.add_widget(box_3)

        def actualizar_evento(x):
            if tf_titulo.text and tf_fecha.text:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE agenda SET titulo = ?, fecha = ?, categoria = ? WHERE id = ?",
                    (tf_titulo.text, tf_fecha.text, tf_cat.text or "Evento / Fecha", agenda_id)
                )
                conn.commit()
                conn.close()
                self.dialog.dismiss()
                self.cargar_agenda()

        self.dialog = MDDialog(
            MDDialogHeadlineText(text="Editar Evento o Trámite"),
            MDDialogContentContainer(
                content,
                orientation="vertical",
            ),
            MDDialogButtonContainer(
                MDButton(MDButtonText(text="Cancelar"), style="text", on_release=lambda x: self.dialog.dismiss()),
                MDButton(MDButtonText(text="Guardar Cambios"), style="filled", on_release=actualizar_evento),
                spacing=dp(8),
            )
        )
        self.dialog.open()

    def eliminar_evento(self, e_id):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM agenda_items WHERE agenda_id = ?", (e_id,))
        cursor.execute("DELETE FROM agenda WHERE id = ?", (e_id,))
        conn.commit()
        conn.close()
        self.cargar_agenda()

    def modal_agregar_truck(self, instance):
        tf_nombre = MDTextField(hint_text="Nombre del Tráiler")
        tf_patente = MDTextField(hint_text="Patente / Dominio")

        logo_seleccionado = {"path": ""}
        lbl_logo_info = MDLabel(text="Ningún logo seleccionado", theme_text_color="Secondary", size_hint_y=None,
                                height=dp(24))

        def elegir_logo(x):
            if has_filechooser:
                filechooser.open_file(
                    title="Selecciona el logo del Food Truck",
                    filters=[("Imágenes", "*.png", "*.jpg", "*.jpeg")],
                    on_selection=lambda seleccion: procesar_seleccion(seleccion, logo_seleccionado, lbl_logo_info)
                )
            else:
                lbl_logo_info.text = "Plyer no disponible para elegir archivo"

        btn_logo = MDButton(
            MDButtonText(text="Seleccionar Logo (Imagen)"),
            style="outlined",
            size_hint_y=None,
            height=dp(36),
            on_release=elegir_logo
        )

        content = MDBoxLayout(orientation="vertical", spacing=dp(10), size_hint_y=None, height=dp(190))
        content.add_widget(tf_nombre)
        content.add_widget(tf_patente)
        content.add_widget(btn_logo)
        content.add_widget(lbl_logo_info)

        def guardar(x):
            if tf_nombre.text:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute("INSERT INTO food_trucks (nombre, patente, logo) VALUES (?, ?, ?)",
                               (tf_nombre.text, tf_patente.text, logo_seleccionado["path"]))
                conn.commit()
                conn.close()
                self.dialog.dismiss()
                self.cargar_trucks()

        self.dialog = MDDialog(
            MDDialogHeadlineText(text="Agregar Nuevo Food Truck"),
            MDDialogContentContainer(
                content,
                orientation="vertical",
            ),
            MDDialogButtonContainer(
                MDButton(MDButtonText(text="Cancelar"), style="text", on_release=lambda x: self.dialog.dismiss()),
                MDButton(MDButtonText(text="Guardar"), style="filled", on_release=guardar),
                spacing=dp(8),
            )
        )
        self.dialog.open()

    def modal_editar_truck(self, instance):
        if not self.current_truck_id:
            return

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT nombre, patente, logo FROM food_trucks WHERE id = ?", (self.current_truck_id,))
        row = cursor.fetchone()
        conn.close()

        tf_nombre = MDTextField(text=row[0] if row else "", hint_text="Nombre del Tráiler")
        tf_patente = MDTextField(text=row[1] if row else "", hint_text="Patente")

        logo_seleccionado = {"path": row[2] if row else ""}
        nombre_logo_actual = os.path.basename(logo_seleccionado["path"]) if logo_seleccionado[
            "path"] else "Ningún logo seleccionado"
        lbl_logo_info = MDLabel(text=nombre_logo_actual, theme_text_color="Secondary", size_hint_y=None, height=dp(24))

        def elegir_logo(x):
            if has_filechooser:
                filechooser.open_file(
                    title="Selecciona el logo del Food Truck",
                    filters=[("Imágenes", "*.png", "*.jpg", "*.jpeg")],
                    on_selection=lambda seleccion: procesar_seleccion(seleccion, logo_seleccionado, lbl_logo_info)
                )
            else:
                lbl_logo_info.text = "Plyer no disponible para elegir archivo"

        btn_logo = MDButton(
            MDButtonText(text="Cambiar Logo (Imagen)"),
            style="outlined",
            size_hint_y=None,
            height=dp(36),
            on_release=elegir_logo
        )

        content = MDBoxLayout(orientation="vertical", spacing=dp(10), size_hint_y=None, height=dp(190))
        content.add_widget(tf_nombre)
        content.add_widget(tf_patente)
        content.add_widget(btn_logo)
        content.add_widget(lbl_logo_info)

        def actualizar(x):
            if tf_nombre.text:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute("UPDATE food_trucks SET nombre = ?, patente = ?, logo = ? WHERE id = ?",
                               (tf_nombre.text, tf_patente.text, logo_seleccionado["path"], self.current_truck_id))
                conn.commit()
                conn.close()
                self.dialog.dismiss()
                self.cargar_trucks()

        self.dialog = MDDialog(
            MDDialogHeadlineText(text="Editar Food Truck Actual"),
            MDDialogContentContainer(
                content,
                orientation="vertical",
            ),
            MDDialogButtonContainer(
                MDButton(MDButtonText(text="Cancelar"), style="text", on_release=lambda x: self.dialog.dismiss()),
                MDButton(MDButtonText(text="Actualizar"), style="filled", on_release=actualizar),
                spacing=dp(8),
            )
        )
        self.dialog.open()

    def modal_checklist(self, agenda_id, titulo_agenda):
        content = MDBoxLayout(orientation="vertical", spacing=dp(12), size_hint_y=None, height=dp(280))
        scroll = MDScrollView()
        list_items = MDList()
        scroll.add_widget(list_items)

        tf_nuevo_subitem = MDTextField(hint_text="Nueva tarea / Ítem pendiente")

        def refrescar_items():
            list_items.clear_widgets()
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT id, item, completado FROM agenda_items WHERE agenda_id = ?", (agenda_id,))
            for sub_id, sub_item, comp in cursor.fetchall():
                box_row = MDBoxLayout(orientation="horizontal", size_hint_y=None, height=dp(45), spacing=dp(8))
                chk = MDCheckbox(active=bool(comp), size_hint_x=0.15)
                chk.bind(active=lambda chk_obj, val, s_id=sub_id: self.toggle_item(s_id, val))
                lbl = MDLabel(text=sub_item, size_hint_x=0.65)
                btn_del = MDIconButton(icon="close", size_hint_x=0.2,
                                       on_release=lambda x, s_id=sub_id: borrar_subitem(s_id))

                box_row.add_widget(chk)
                box_row.add_widget(lbl)
                box_row.add_widget(btn_del)
                list_items.add_widget(box_row)
            conn.close()

        def agregar_subitem(x):
            if tf_nuevo_subitem.text:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute("INSERT INTO agenda_items (agenda_id, item, completado) VALUES (?, ?, 0)",
                               (agenda_id, tf_nuevo_subitem.text))
                conn.commit()
                conn.close()
                tf_nuevo_subitem.text = ""
                refrescar_items()

        def borrar_subitem(s_id):
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM agenda_items WHERE id = ?", (s_id,))
            conn.commit()
            conn.close()
            refrescar_items()

        refrescar_items()

        box_add = MDBoxLayout(orientation="horizontal", spacing=dp(8), size_hint_y=None, height=dp(50))
        box_add.add_widget(tf_nuevo_subitem)
        box_add.add_widget(MDIconButton(icon="plus", on_release=agregar_subitem))

        content.add_widget(scroll)
        content.add_widget(box_add)

        self.dialog = MDDialog(
            MDDialogHeadlineText(text=f"Tareas: {titulo_agenda}"),
            MDDialogContentContainer(
                content,
                orientation="vertical",
            ),
            MDDialogButtonContainer(
                MDButton(MDButtonText(text="Cerrar"), style="text", on_release=lambda x: self.dialog.dismiss()),
                spacing=dp(8),
            )
        )
        self.dialog.open()

    def toggle_item(self, sub_id, estado):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("UPDATE agenda_items SET completado = ? WHERE id = ?", (1 if estado else 0, sub_id))
        conn.commit()
        conn.close()


def procesar_seleccion(seleccion, dict_ref, label_ref):
    if seleccion:
        ruta_archivo = seleccion[0]
        dict_ref["path"] = ruta_archivo
        label_ref.text = os.path.basename(ruta_archivo)


if __name__ == "__main__":
    FoodTruckApp().run()