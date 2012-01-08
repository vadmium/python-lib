import tkinter
from tkinter.ttk import Label

def add_field(window, row, label, widget):
    Label(window, text=label).grid(
        row=row, column=0, sticky=tkinter.E + tkinter.W)
    widget.grid(row=row, column=1, sticky=tkinter.E + tkinter.W)
