.PHONY: test demo present client evidence attack attack-evidence clean help

help:
	@echo "Uso: make <target>"
	@echo ""
	@echo "Targets disponibles:"
	@echo "  test          Ejecutar suite de pruebas"
	@echo "  demo          Iniciar proyecto completo (servidor TCP + frontend)"
	@echo "  present       Iniciar modo presentación con clientes reales persistentes"
	@echo "  client        Lanzar un cliente real persistente (MODE/NODE_ID/INTERVAL)"
	@echo "  evidence      Generar artefactos de evidencia en artifacts/demo/"
	@echo "  attack        Ejecutar simulador de ataques contra servidor local"
	@echo "  attack-evidence  Generar artefactos de ataque (evidence + attack)"
	@echo "  clean         Limpiar artefactos, logs y base de datos"
	@echo "  help          Mostrar esta ayuda"

test:
	@echo "=== Ejecutando pruebas ==="
	python3 -m unittest discover -s tests -v

demo:
	@echo "=== Iniciando proyecto ==="
	bash ./scripts/run_project.sh

present:
	@echo "=== Iniciando modo presentación ==="
	bash ./scripts/run_presentation.sh 8080 $${PROFILE:-multi-node}

client:
	@echo "=== Lanzando cliente persistente ==="
	bash ./scripts/run_client.sh $${MODE:-normal} $${NODE_ID:-node-01} $${INTERVAL:-3.0}

evidence:
	@echo "=== Generando artefactos de evidencia ==="
	bash ./scripts/generate_demo_artifacts.sh
	bash ./scripts/generate_attack_evidence.sh

attack:
	@echo "=== Ejecutando simulador de ataques ==="
	python3 -m attacker.attack_simulator --attack all --timeout 2.0 --full

attack-evidence:
	@echo "=== Generando artefactos de evidencia (ataques) ==="
	bash ./scripts/generate_attack_evidence.sh

clean:
	@echo "=== Limpiando artefactos, logs y base de datos ==="
	rm -rf artifacts/demo/
	rm -rf artifacts/screenshots/
	rm -rf logs/
	rm -rf captures/
	rm -f data/monitor.db data/monitor.db-wal data/monitor.db-shm
	@echo "Hecho."
