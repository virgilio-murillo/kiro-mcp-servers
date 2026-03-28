#!/usr/bin/env python3
"""Tab picker with checkboxes. Reads tab list from stdin (JSON), shows GUI, prints selected indices."""
import json, sys, tkinter as tk

def main():
    tabs = json.loads(sys.stdin.read())
    if not tabs:
        sys.exit(1)

    root = tk.Tk()
    root.title("Select Tabs")
    root.attributes("-topmost", True)
    root.lift()
    root.focus_force()

    w, h = 600, min(40 * len(tabs) + 120, 500)
    root.geometry(f"{w}x{h}+{(root.winfo_screenwidth()-w)//2}+{(root.winfo_screenheight()-h)//2}")

    tk.Label(root, text="Pick tabs to read:", font=("Helvetica", 14), pady=8).pack(side="top")

    # Buttons FIRST so they always show
    btn_frame = tk.Frame(root, pady=8)
    btn_frame.pack(side="bottom")
    vars = []

    def submit():
        print(json.dumps([i for i, v in enumerate(vars) if v.get()]))
        root.destroy()

    def cancel():
        print("[]")
        root.destroy()

    tk.Button(btn_frame, text="Cancel", command=cancel, width=10).pack(side="left", padx=5)
    tk.Button(btn_frame, text="Continue", command=submit, width=10, default="active").pack(side="left", padx=5)

    # Scrollable checkboxes fill remaining space
    frame = tk.Frame(root)
    frame.pack(side="top", fill="both", expand=True, padx=10)
    canvas = tk.Canvas(frame)
    scrollbar = tk.Scrollbar(frame, orient="vertical", command=canvas.yview)
    inner = tk.Frame(canvas)
    inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.create_window((0, 0), window=inner, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    for tab in tabs:
        v = tk.BooleanVar()
        tk.Checkbutton(inner, text=tab, variable=v, anchor="w", font=("Helvetica", 12)).pack(fill="x", pady=1)
        vars.append(v)

    root.bind("<Return>", lambda e: submit())
    root.bind("<Escape>", lambda e: cancel())
    root.mainloop()

if __name__ == "__main__":
    main()
