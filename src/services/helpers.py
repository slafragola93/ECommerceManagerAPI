from fastapi import HTTPException


class Helpers:
    @staticmethod
    def parse_int_list(s):
        """Gestisce la conversione di stringhe in liste di interi e lancia un'eccezione se il formato non è corretto."""
        try:
            return [int(item) for item in s.split(',')]
        except ValueError:
            raise ValueError("Input non valido, separare gli elementi con una virgola.")