"""
Laus Cognition & Skills Hub - Interpretador de SKILL.md (Pilar 5)
Lê e valida em tempo real as instruções e parâmetros contidos em arquivos markdown operacionais.
"""
import os
import re
from typing import Dict, Any

class SkillInterpreter:
    def __init__(self, skill_path: str):
        self.skill_path = skill_path
        self.raw_content = ""
        self.parameters: Dict[str, Any] = {}

    def load_and_parse(self) -> Dict[str, Any]:
        """Lê o arquivo markdown e extrai os parâmetros estruturados por Regex."""
        if not os.path.exists(self.skill_path):
            raise FileNotFoundError(f"Arquivo de especificação não localizado em: {self.skill_path}")
            
        with open(self.skill_path, "r", encoding="utf-8") as f:
            self.raw_content = f.read()

        # Regex para capturar linhas de parâmetros no formato "- CHAVE: VALOR"
        param_pattern = re.compile(r"-\s+([A-Z_]+):\s*(.*)")
        
        for line in self.raw_content.splitlines():
            match = param_pattern.match(line)
            if match:
                key = match.group(1).strip()
                val = match.group(2).strip()
                
                # Tratamento de tipos nativos (floats, ints, strings)
                if val.startswith('"') and val.endswith('"'):
                    val = val.strip('"')
                elif "." in val:
                    try: val = float(val)
                    except ValueError: pass
                else:
                    try: val = int(val)
                    except ValueError: pass
                    
                self.parameters[key] = val
                
        return self.parameters

    def validate_against_env(self, detected_spread: float, targeted_volume: float) -> bool:
        """Valida se as condições de mercado atuais violam a SKILL.md carregada."""
        if not self.parameters:
            self.load_and_parse()
            
        min_spread = self.parameters.get("MIN_SPREAD_REQ", 0.0)
        
        if detected_spread < min_spread:
            print(f"⚠️ [SKILL VALIDATION] Rejeitado: Spread de {detected_spread}% abaixo do mínimo exigido de {min_spread}%")
            return False
            
        return True
