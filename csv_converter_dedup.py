#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import csv
import random
import io
from datetime import datetime

# Список ZIP-кодов Флориды
FLORIDA_ZIPS = [
    '32801', '32803', '32804', '32805', '32806', '32807', '32808', '32809',
    '33125', '33126', '33127', '33128', '33129', '33130', '33131', '33132',
    '33133', '33134', '33135', '33136', '33137', '33138', '33139', '33140',
    '33301', '33304', '33305', '33306', '33308', '33309', '33311', '33312',
    '33060', '33062', '33063', '33064', '33065', '33066', '33067', '33068',
    '33401', '33403', '33404', '33405', '33406', '33407', '33408', '33409',
    '33510', '33511', '33534', '33547', '33548', '33549', '33556', '33558',
    '33701', '33702', '33703', '33704', '33705', '33706', '33707', '33708',
    '34101', '34102', '34103', '34104', '34105', '34106', '34108', '34109',
    '32003', '32034', '32065', '32073', '32080', '32081', '32082', '32092',
]

FLORIDA_AREA_CODES = ['239', '305', '321', '352', '386', '407', '561', '727', '754', '772', '786', '813', '850', '863', '904', '941', '954']

def generate_email(first_name, last_name):
    domains = ['gmail.com', 'yahoo.com', 'outlook.com', 'hotmail.com', 'aol.com']
    patterns = [
        f"{first_name.lower()}.{last_name.lower()}",
        f"{first_name.lower()}{last_name.lower()}",
        f"{first_name.lower()}{random.randint(1, 999)}",
        f"{first_name.lower()}.{last_name.lower()}{random.randint(1, 99)}",
        f"{first_name[0].lower()}{last_name.lower()}",
    ]
    email_pattern = random.choice(patterns)
    domain = random.choice(domains)
    return f"{email_pattern}@{domain}"

def generate_phone(area_code=None):
    if area_code is None:
        area_code = random.choice(FLORIDA_AREA_CODES)
    middle = random.randint(200, 999)
    last = random.randint(1000, 9999)
    return f"{area_code}{middle}{last}"

def format_name(name):
    if not name:
        return None
    return name.strip().capitalize()

def convert_row(row):
    try:
        if len(row) < 11:
            return None

        first_name = row[1].strip() if len(row) > 1 else ''
        last_name = row[2].strip() if len(row) > 2 else ''
        date_str = row[5].strip() if len(row) > 5 else ''

        if not all([first_name, last_name, date_str]) or len(date_str) != 8:
            return None

        try:
            year = date_str[0:4]
            month = date_str[4:6]
            day = date_str[6:8]
            datetime(int(year), int(month), int(day))

            if int(day) == 1 and int(month) == 1:
                return None
        except (ValueError, IndexError):
            return None

        first_name = format_name(first_name)
        last_name = format_name(last_name)

        if not first_name or not last_name:
            return None

        random_number = random.randint(1, 500)
        random_zip = random.choice(FLORIDA_ZIPS)
        email = generate_email(first_name, last_name)
        phone = generate_phone()

        output_row = [
            random_zip, month, day, year, first_name, last_name,
            str(random_number), email, phone
        ]
        return output_row
    except Exception as e:
        return None

class CSVConverterGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("CSV Конвертер (с дедупликацией)")
        self.root.geometry("1200x750")
        self.root.configure(bg='#f0f0f0')
        self.converted_data = []
        self.create_widgets()

    def create_widgets(self):
        # Заголовок
        title_frame = tk.Frame(self.root, bg='#2c3e50', height=70)
        title_frame.pack(fill=tk.X)
        title_frame.pack_propagate(False)

        title_label = tk.Label(title_frame, text="🔄 CSV Конвертер",
                              font=('Arial', 20, 'bold'),
                              bg='#2c3e50', fg='white')
        title_label.pack(pady=10)

        subtitle_label = tk.Label(title_frame, text="Длинный формат → Короткий формат (9 полей) | 🔍 Дедупликация по дате и ФИО",
                                 font=('Arial', 10), bg='#2c3e50', fg='#ecf0f1')
        subtitle_label.pack()

        # Основной контейнер
        main_frame = tk.Frame(self.root, bg='#f0f0f0')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Левая панель
        left_frame = tk.LabelFrame(main_frame, text="📥 Входные данные",
                                  font=('Arial', 12, 'bold'),
                                  bg='#f0f0f0', fg='#2c3e50', padx=15, pady=15)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        button_frame = tk.Frame(left_frame, bg='#f0f0f0')
        button_frame.pack(fill=tk.X, pady=(0, 10))

        load_btn = tk.Button(button_frame, text="📁 Загрузить CSV", command=self.load_file,
                            bg='#3498db', fg='white', font=('Arial', 10, 'bold'),
                            relief=tk.FLAT, padx=15, pady=10, cursor='hand2')
        load_btn.pack(side=tk.LEFT, padx=(0, 5))

        clear_btn = tk.Button(button_frame, text="🗑️ Очистить", command=self.clear_input,
                             bg='#e74c3c', fg='white', font=('Arial', 10, 'bold'),
                             relief=tk.FLAT, padx=15, pady=10, cursor='hand2')
        clear_btn.pack(side=tk.LEFT)

        info_frame = tk.Frame(left_frame, bg='#fff3cd', relief=tk.SOLID, borderwidth=1)
        info_frame.pack(fill=tk.X, pady=(0, 10))

        tk.Label(info_frame, text="📋 Формат: 2020003823,BMW,MONSTER,H,,19420331,1761,...",
                font=('Courier New', 8), bg='#fff3cd', fg='#555').pack(padx=10, pady=5)

        self.input_text = scrolledtext.ScrolledText(left_frame, height=20,
                                                    font=('Courier New', 9), wrap=tk.WORD,
                                                    bg='white', relief=tk.SOLID, borderwidth=1)
        self.input_text.pack(fill=tk.BOTH, expand=True, pady=(5, 10))

        hint_frame = tk.Frame(left_frame, bg='#d1ecf1', relief=tk.SOLID, borderwidth=1)
        hint_frame.pack(fill=tk.X, pady=(0, 10))
        tk.Label(hint_frame, text="💡 Минимум 11 полей. Даты 01.01.* пропускаются. Дубликаты по дате+ФИО удаляются",
                font=('Arial', 8), bg='#d1ecf1', fg='#0c5460').pack(padx=10, pady=5)

        convert_btn = tk.Button(left_frame, text="⚡ Конвертировать", command=self.convert_data,
                               bg='#27ae60', fg='white', font=('Arial', 12, 'bold'),
                               relief=tk.FLAT, padx=20, pady=12, cursor='hand2')
        convert_btn.pack(fill=tk.X)

        # Правая панель
        right_frame = tk.LabelFrame(main_frame, text="📤 Результат",
                                   font=('Arial', 12, 'bold'),
                                   bg='#f0f0f0', fg='#2c3e50', padx=15, pady=15)
        right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        export_frame = tk.Frame(right_frame, bg='#f0f0f0')
        export_frame.pack(fill=tk.X, pady=(0, 10))

        export_btn = tk.Button(export_frame, text="💾 Сохранить", command=self.save_file,
                              bg='#9b59b6', fg='white', font=('Arial', 10, 'bold'),
                              relief=tk.FLAT, padx=15, pady=10, cursor='hand2')
        export_btn.pack(side=tk.LEFT, padx=(0, 5))

        copy_btn = tk.Button(export_frame, text="📋 Копировать", command=self.copy_output,
                            bg='#16a085', fg='white', font=('Arial', 10, 'bold'),
                            relief=tk.FLAT, padx=15, pady=10, cursor='hand2')
        copy_btn.pack(side=tk.LEFT)

        output_info_frame = tk.Frame(right_frame, bg='#d4edda', relief=tk.SOLID, borderwidth=1)
        output_info_frame.pack(fill=tk.X, pady=(0, 10))
        tk.Label(output_info_frame, text="✨ Результат: 33071,03,31,1942,Bmw,Monster,444,email@gmail.com,8843344141",
                font=('Courier New', 8), bg='#d4edda', fg='#155724').pack(padx=10, pady=5)

        self.output_text = scrolledtext.ScrolledText(right_frame, height=20,
                                                     font=('Courier New', 9), wrap=tk.NONE,
                                                     bg='#ecf0f1', relief=tk.SOLID, borderwidth=1,
                                                     state=tk.DISABLED)
        self.output_text.pack(fill=tk.BOTH, expand=True, pady=(5, 10))

        self.status_label = tk.Label(right_frame, text="Готов к работе",
                                     font=('Arial', 9, 'bold'), bg='#f0f0f0',
                                     fg='#7f8c8d', anchor=tk.W)
        self.status_label.pack(fill=tk.X)

    def load_file(self):
        filename = filedialog.askopenfilename(
            title="Выберите CSV файл",
            filetypes=[("CSV файлы", "*.csv"), ("Все файлы", "*.*")]
        )
        if filename:
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    content = f.read()
                    self.input_text.delete('1.0', tk.END)
                    self.input_text.insert('1.0', content)
                    self.status_label.config(text=f"✓ Загружен: {filename.split('/')[-1]}", fg='#27ae60')
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось загрузить:\n{str(e)}")

    def clear_input(self):
        self.input_text.delete('1.0', tk.END)
        self.status_label.config(text="Очищено", fg='#7f8c8d')

    def convert_data(self):
        input_data = self.input_text.get('1.0', tk.END).strip()
        if not input_data:
            messagebox.showwarning("Предупреждение", "Введите данные")
            return

        csv_reader = csv.reader(io.StringIO(input_data))
        self.converted_data = []
        converted_count = 0
        skipped_count = 0
        duplicate_count = 0

        # Set для отслеживания уникальных комбинаций (year, month, day, first_name, last_name)
        seen_records = set()

        for row in csv_reader:
            if not row or len(row) < 11:
                skipped_count += 1
                continue

            converted = convert_row(row)
            if converted:
                # Извлекаем поля для проверки дубликатов
                # converted = [zip, month, day, year, first_name, last_name, random_number, email, phone]
                # Индексы: 0=zip, 1=month, 2=day, 3=year, 4=first_name, 5=last_name
                month = converted[1]
                day = converted[2]
                year = converted[3]
                first_name = converted[4].lower()  # Приводим к lowercase для корректного сравнения
                last_name = converted[5].lower()   # Приводим к lowercase для корректного сравнения

                # Создаем уникальный ключ
                unique_key = (year, month, day, first_name, last_name)

                # Проверяем, был ли уже такой записи
                if unique_key in seen_records:
                    duplicate_count += 1
                    continue

                # Добавляем в set и в результаты
                seen_records.add(unique_key)
                self.converted_data.append(converted)
                converted_count += 1
            else:
                skipped_count += 1

        self.display_output()

        status_text = f"✓ Конвертировано: {converted_count} | ✗ Пропущено: {skipped_count}"
        if duplicate_count > 0:
            status_text += f" | 🔍 Дубликатов: {duplicate_count}"

        self.status_label.config(text=status_text, fg='#27ae60')

        if converted_count == 0:
            messagebox.showinfo("Информация", "Ни одной строки не конвертировано.\nПроверьте формат данных.")

    def display_output(self):
        self.output_text.config(state=tk.NORMAL)
        self.output_text.delete('1.0', tk.END)
        header = "Field1,Field2,Field3,Field4,Field5,Field6,Field7,Field8,Field9\n"
        self.output_text.insert('1.0', header)

        output = io.StringIO()
        writer = csv.writer(output)
        for row in self.converted_data:
            writer.writerow(row)
        self.output_text.insert(tk.END, output.getvalue())
        self.output_text.config(state=tk.DISABLED)

    def save_file(self):
        if not self.converted_data:
            messagebox.showwarning("Предупреждение", "Нет данных для сохранения")
            return

        filename = filedialog.asksaveasfilename(
            title="Сохранить CSV",
            defaultextension=".csv",
            filetypes=[("CSV файлы", "*.csv"), ("Все файлы", "*.*")]
        )
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(['Field1', 'Field2', 'Field3', 'Field4', 'Field5',
                                   'Field6', 'Field7', 'Field8', 'Field9'])
                    for row in self.converted_data:
                        writer.writerow(row)
                messagebox.showinfo("Успех", f"Сохранено:\n{filename}")
                self.status_label.config(text=f"✓ Сохранено", fg='#9b59b6')
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось сохранить:\n{str(e)}")

    def copy_output(self):
        if not self.converted_data:
            messagebox.showwarning("Предупреждение", "Нет данных")
            return

        output_lines = ["Field1,Field2,Field3,Field4,Field5,Field6,Field7,Field8,Field9"]
        output = io.StringIO()
        writer = csv.writer(output)
        for row in self.converted_data:
            writer.writerow(row)
        output_lines.append(output.getvalue())

        self.root.clipboard_clear()
        self.root.clipboard_append('\n'.join(output_lines))
        messagebox.showinfo("Успех", "Скопировано в буфер обмена")
        self.status_label.config(text="✓ Скопировано", fg='#16a085')

def main():
    root = tk.Tk()
    app = CSVConverterGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
