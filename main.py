import tkinter as tk
from tkinter import ttk
import threading
import pyperclip
import keyboard
from google import genai
import ctypes

# setx GEMINI_API_KEY "colle-ta-clé-ici"`.
client = genai.Client()

# Modèles disponibles
MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite", 
    "gemini-3-flash",
]

# fenêtre sans focus
GWL_EXSTYLE = -20
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOPMOST = 0x00000008
WS_EX_TOOLWINDOW = 0x00000080


class OverlayApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("AskAI - Réponse")
        
        self.root.attributes('-topmost', True)  
        self.root.attributes('-alpha', 0.95)  
        self.root.overrideredirect(True)  
        
        window_width = 350
        window_height = 200
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = screen_width - window_width - 10
        y = screen_height - window_height - 50
        self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")
        
        self.root.update_idletasks()
        self.set_no_activate()
        
        self.drag_x = 0
        self.drag_y = 0
        
        self.root.configure(bg='#ffffff')
        
        main_frame = tk.Frame(self.root, bg='#ffffff')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        
        main_frame.bind('<Button-1>', self.start_drag)
        main_frame.bind('<B1-Motion>', self.do_drag)
        self.root.bind('<Button-1>', self.start_drag)
        self.root.bind('<B1-Motion>', self.do_drag)
        
        self.status_label = tk.Label(
            main_frame, 
            text="⬆ Sélectionnez du texte et appuyez sur Flèche Haut",
            bg='#ffffff', 
            fg='#666666',
            font=('Segoe UI', 8)
        )
        self.status_label.pack(anchor='w', pady=(0, 5))
        
        text_frame = tk.Frame(main_frame, bg='#ffffff')
        text_frame.pack(fill=tk.BOTH, expand=True)
        
        self.scrollbar = ttk.Scrollbar(text_frame)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.response_text = tk.Text(
            text_frame,
            wrap=tk.WORD,
            bg='#f5f5f5',
            fg='#333333',
            font=('Segoe UI', 10),
            relief=tk.FLAT,
            padx=8,
            pady=8,
            yscrollcommand=self.scrollbar.set
        )
        self.response_text.pack(fill=tk.BOTH, expand=True)
        self.scrollbar.config(command=self.response_text.yview)
        
        help_label = tk.Label(
            main_frame,
            text="⬆ Envoyer | ⬇ Masquer",
            bg='#ffffff',
            fg='#999999',
            font=('Segoe UI', 7)
        )
        help_label.pack(anchor='e', pady=(5, 0))
        
        self.is_visible = True
        self.is_ghost_mode = False
        
        self.current_model_index = 0
        
        self.original_bg = '#ffffff'
        self.original_text_bg = '#f5f5f5'
        self.original_text_fg = '#333333'
        
        self.setup_hotkeys()
        
        self.response_text.insert(tk.END, "En attente...\n\nSélectionnez du texte, puis ⬆")
        self.response_text.config(state=tk.DISABLED)
        
    def set_no_activate(self):
        """Configure la fenêtre pour ne pas prendre le focus"""
        try:
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            # Ajouter WS_EX_NOACTIVATE et WS_EX_TOOLWINDOW pour ne pas prendre le focus
            new_style = style | WS_EX_NOACTIVATE | WS_EX_TOPMOST | WS_EX_TOOLWINDOW
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, new_style)
        except Exception as e:
            print(f"Impossible de configurer le mode no-activate: {e}")
        
    def start_drag(self, event):
        """Début du drag de la fenêtre"""
        self.drag_x = event.x
        self.drag_y = event.y
        
    def do_drag(self, event):
        """Déplacement de la fenêtre"""
        x = self.root.winfo_x() + event.x - self.drag_x
        y = self.root.winfo_y() + event.y - self.drag_y
        self.root.geometry(f"+{x}+{y}")
        
    def setup_hotkeys(self):
        """Configure les raccourcis clavier globaux"""
        keyboard.on_press_key('up', self.on_up_arrow, suppress=False)
        keyboard.on_press_key('down', self.on_down_arrow, suppress=False)
        keyboard.on_press_key('right', self.on_right_arrow, suppress=False)
        keyboard.on_press_key('left', self.on_left_arrow, suppress=False)
        
    def on_left_arrow(self, event):
        """Change de modèle"""
        self.root.after(0, self.cycle_model)
        
    def cycle_model(self):
        """Passe au modèle suivant"""
        self.current_model_index = (self.current_model_index + 1) % len(MODELS)
        current_model = MODELS[self.current_model_index]
        self.update_status(f" {current_model}")

        models_list = []
        for i, m in enumerate(MODELS):
            if i == self.current_model_index:
                models_list.append(f"  ▶ {m} (actif)")
            else:
                models_list.append(f"  • {m}")
        info_text = f"Modèle: {current_model}\n\nModèles disponibles:\n" + "\n".join(models_list)
        self.set_response(info_text)
        
    def get_current_model(self):
        """Retourne le modèle actuel"""
        return MODELS[self.current_model_index]
        
    def try_next_model(self):
        """Passe au modèle suivant si disponible (pour fallback)"""
        if self.current_model_index < len(MODELS) - 1:
            self.current_model_index += 1
            return True
        return False
        
    def on_up_arrow(self, event):
        """Appelé quand la flèche haut est pressée"""
        # Multithread
        threading.Thread(target=self.process_selection, daemon=True).start()
        
    def on_down_arrow(self, event):
        """Toggle la visibilité de l'overlay"""
        self.root.after(0, self.toggle_visibility)
        
    def toggle_visibility(self):
        """Affiche ou masque la fenêtre"""
        if self.is_visible:
            self.root.withdraw()
            self.is_visible = False
        else:
            self.root.deiconify()
            self.is_visible = True
            
    def on_right_arrow(self, event):
        """Toggle le mode ghost (transparent)"""
        self.root.after(0, self.toggle_ghost_mode)
        
    def toggle_ghost_mode(self):
        """Active/désactive le mode transparent"""
        transparent_color = '#010101'
        
        if self.is_ghost_mode:
            self.root.attributes('-transparentcolor', '')
            self.root.configure(bg=self.original_bg)
            for widget in self.root.winfo_children():
                self.reset_widget_colors(widget)
            self.response_text.config(bg=self.original_text_bg)
            self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            self.is_ghost_mode = False
        else:
            self.root.attributes('-transparentcolor', transparent_color)
            self.root.configure(bg=transparent_color)
            for widget in self.root.winfo_children():
                self.set_widget_ghost(widget, transparent_color)
            self.response_text.config(bg=transparent_color)
            self.scrollbar.pack_forget()
            self.is_ghost_mode = True
            
    def reset_widget_colors(self, widget):
        """Réinitialise les couleurs d'un widget"""
        if widget == self.response_text:
            return
        try:
            widget.configure(bg=self.original_bg)
        except:
            pass
        for child in widget.winfo_children():
            self.reset_widget_colors(child)
            
    def set_widget_ghost(self, widget, transparent_color):
        """Met un widget en mode ghost"""
        if widget == self.response_text:
            return
        try:
            widget.configure(bg=transparent_color, fg='#ffffff')
        except:
            try:
                widget.configure(bg=transparent_color)
            except:
                pass
        for child in widget.winfo_children():
            self.set_widget_ghost(child, transparent_color)
            
    def get_selected_text(self):
        """Récupère le texte sélectionné via le presse-papier"""
        try:
            old_clipboard = pyperclip.paste()
        except:
            old_clipboard = ""
            
        keyboard.press_and_release('ctrl+c')

        import time
        time.sleep(0.1)

        try:
            selected_text = pyperclip.paste()
        except:
            selected_text = ""
            
        # Si le texte est le même qu'avant, pas de nouvelle sélection
        if selected_text == old_clipboard:
            return None
            
        return selected_text
        
    def process_selection(self):
        """Traite le texte sélectionné"""
        self.root.after(0, lambda: self.update_status(" Récupération de la sélection..."))
        
        selected_text = self.get_selected_text()
        
        if not selected_text or selected_text.strip() == "":
            self.root.after(0, lambda: self.update_status(" Aucun texte sélectionné"))
            return
            
        self.root.after(0, self.show_window)
        
        self.root.after(0, lambda: self.update_status(" Envoi à l'IA..."))
        self.root.after(0, lambda: self.set_response("Chargement en cours..."))
        
        prompt = f"Donne moi juste la réponse sans justification:\n\n{selected_text}"
        
        start_index = self.current_model_index
        
        for attempt in range(len(MODELS)):
            current_model = self.get_current_model()
            self.root.after(0, lambda m=current_model: self.update_status(f" {m}..."))
            
            try:
                response = client.models.generate_content(
                    model=current_model,
                    contents=prompt
                )
                
                answer = response.text
                self.root.after(0, lambda: self.set_response(answer))
                self.root.after(0, lambda m=current_model: self.update_status(f" {m}"))
                return
                
            except Exception as e:
                error_str = str(e).lower()
                if "quota" in error_str or "rate" in error_str or "limit" in error_str or "429" in error_str or "resource" in error_str:
                    if self.try_next_model():
                        next_model = self.get_current_model()
                        self.root.after(0, lambda m=next_model: self.update_status(f" Quota épuisé, essai {m}..."))
                        continue
                    else:
                        self.current_model_index = start_index
                        self.root.after(0, lambda: self.set_response("Tous les modèles ont atteint leur quota."))
                        self.root.after(0, lambda: self.update_status(" Quotas épuisés"))
                        return
                else:
                    error_msg = f"Erreur: {str(e)}"
                    self.root.after(0, lambda msg=error_msg: self.set_response(msg))
                    self.root.after(0, lambda: self.update_status(" Erreur"))
                    return
        
        self.root.after(0, lambda: self.update_status(" Échec après tous les essais"))
            
    def show_window(self):
        """Affiche la fenêtre"""
        self.root.deiconify()
        self.is_visible = True
        
    def update_status(self, text):
        """Met à jour le label de statut"""
        self.status_label.config(text=text)
        
    def set_response(self, text):
        """Met à jour la zone de réponse"""
        self.response_text.config(state=tk.NORMAL)
        self.response_text.delete(1.0, tk.END)
        self.response_text.insert(tk.END, text)
        self.response_text.config(state=tk.DISABLED)
        
    def run(self):
        """Lance l'application"""
        print("AskAI démarré!")
        print("- Sélectionnez du texte et appuyez sur Flèche Haut pour poser une question")
        print("- Appuyez sur Flèche Bas pour afficher/masquer l'overlay")
        print("- Fermez la fenêtre pour quitter")
        self.root.mainloop()
        
    def cleanup(self):
        """Nettoie les ressources"""
        keyboard.unhook_all()


if __name__ == "__main__":
    app = OverlayApp()
    try:
        app.run()
    finally:
        app.cleanup()