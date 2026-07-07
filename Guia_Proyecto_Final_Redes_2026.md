**Redes de Computadores** 

**Proyecto Final** 

## **Universidad de Concepción** 

Facultad de Ingeniería 

Departamento de Ingeniería Informática y Ciencias de la Computación 

## **Redes de Computadores** (501403) **Guía del Proyecto Final** 

Docente: Diego Arroyo Navarrete Semestre: 2026-1 

## **1. Presentación** 

El Proyecto Final de la asignatura consiste en el diseño, implementación y validación de un sistema de monitoreo remoto seguro para un entorno ciberfísico simulado, completamente ejecutable en software sobre los computadores del grupo. 

El proyecto debe integrar contenidos revisados durante el semestre, incluyendo arquitectura de red, servicios, comunicación cliente-servidor, protocolos de transporte, seguridad básica, análisis de tráfico y validación técnica del sistema. 

**Idea central del proyecto.** Cada grupo desarrollará un sistema funcional en el que uno o más nodos simulados generen información de un proceso o entorno, y un componente central reciba, procese, registre, visualice o supervise dicha información mediante comunicación real sobre red. 

## **2. Propósito formativo** 

El proyecto busca que el grupo sea capaz de: 

Diseñar una aplicación de red funcional. 

Implementar comunicación real sobre TCP/IP. 

Justificar decisiones de protocolo, arquitectura y transporte. 

Incorporar una medida básica de seguridad o confiabilidad. 

Analizar el comportamiento de su sistema con herramientas vistas en el curso. 

Presentar, defender y documentar técnicamente una solución completa. 

## **3. Tema marco del proyecto** 

**Tema común obligatorio:** Todos los grupos deberán desarrollar un **sistema de monitoreo remoto seguro para un entorno ciberfísico simulado** . 

**Importante.** El proyecto **no requiere hardware físico** . Las variables del entorno pueden ser completamente simuladas mediante software. 

## **3.1. Ejemplos de variables o escenarios permitidos** 

Cada grupo podrá elegir una variante temática, por ejemplo: 

Monitoreo ambiental remoto. 

Página 1 de 8 

**Redes de Computadores** 

**Proyecto Final** 

Monitoreo de acceso o presencia. 

Monitoreo del estado de equipos o servicios. 

Supervisión de una sala técnica o sistema crítico. 

Proceso industrial simple simulado. 

Sistema de alarmas o eventos en un entorno controlado. 

## **3.2. Ejemplos de variables simuladas** 

El grupo podrá trabajar, por ejemplo, con variables como: 

Temperatura. 

Humedad. 

Estado de puerta. 

- Presencia. 

Nivel de batería. 

Estado de un servicio. 

Nivel de un estanque. 

Presión o velocidad simulada. 

## **4. Restricciones generales** 

El proyecto debe poder desarrollarse completamente con el PC del grupo. 

No se exigirá ni se bonificará el uso de hardware adicional. 

El proyecto debe incluir comunicación real sobre red. 

El proyecto no puede consistir únicamente en una revisión bibliográfica o una presentación teórica. 

- El proyecto no puede basarse solamente en lectura y escritura de archivos sin intercambio real de mensajes por red. 

El proyecto debe ser reproducible por el equipo docente con instrucciones razonables de ejecución. 

El proyecto debe trabajar únicamente sobre el entorno del propio grupo o sobre recursos definidos por el docente para fines académicos. 

## **5. Tamaño de grupo y organización** 

Los grupos serán de **4 estudiantes** . 

Cada grupo deberá declarar integrantes y roles. 

Página 2 de 8 

**Redes de Computadores** 

**Proyecto Final** 

## **5.1. Roles sugeridos** 

Se recomienda distribuir el trabajo con al menos los siguientes roles: 

Responsable de arquitectura y documentación. 

Responsable de nodo o cliente simulado. 

Responsable de servidor, procesamiento o visualización. 

Responsable de pruebas, validación y análisis de red. 

**Observación.** La distribución interna del trabajo no elimina la responsabilidad colectiva sobre el proyecto completo. Todos los integrantes deben ser capaces de defender técnicamente el trabajo realizado. 

## **6. Software recomendado** 

## **6.1. Opción recomendada** 

El software recomendado para el desarrollo del proyecto será **Python** , por su facilidad para implementar clientes, servidores, sockets, registro de datos y prototipos de aplicación de red. 

Se permitirá utilizar otras alternativas si el grupo puede justificarlas técnicamente y si el proyecto sigue siendo completamente ejecutable en el entorno de trabajo del curso. 

## **6.2. Herramientas o bibliotecas posibles** 

A modo orientativo, el grupo puede utilizar: 

`socket` . 

`threading` o `asyncio` . 

`json` . 

`http.server` o `Flask` , si corresponde. 

`sqlite3` , archivos `csv` o `json` , si requieren persistencia simple. 

`tkinter` u otra interfaz simple, si desean incorporar visualización local. 

**Importante.** La complejidad visual no reemplaza la calidad técnica del proyecto. Se evaluará principalmente la arquitectura, la comunicación, la validación y la defensa técnica. 

## **7. Requisitos mínimos del sistema** 

Todo proyecto deberá incluir, como mínimo, los siguientes componentes: 

## **7.1. Nodos simulados** 

Uno o más programas que generen datos o eventos del entorno simulado. 

## **7.2. Servidor o componente central** 

Un programa que reciba información, la procese y la registre, supervise o visualice. 

Página 3 de 8 

**Redes de Computadores** 

**Proyecto Final** 

## **7.3. Comunicación real sobre red** 

Debe existir intercambio real de mensajes entre procesos, por ejemplo mediante: 

Sockets TCP. 

Sockets UDP. 

HTTP u otra API simple. 

## **7.4. Componente básico de seguridad o confiabilidad** 

El proyecto debe incorporar al menos uno de los siguientes elementos: 

Autenticación básica cliente-servidor. 

Validación de mensajes. 

- Mecanismo simple de integridad, como hash o checksum. 

- Control de acceso básico. 

Manejo de reconexión. 

- Detección de mensajes inválidos o anómalos. 

Alertas por condición fuera de rango. 

## **7.5. Validación con herramientas del curso** 

Todo grupo debe incluir: 

Evidencia y análisis con Wireshark. 

Uso de Nmap solo si el proyecto expone un servicio de red y siempre sobre el propio entorno autorizado. 

## **8. Qué no se aceptará como proyecto final** 

No se aceptarán como proyecto final: 

Proyectos puramente bibliográficos. 

Proyectos sin implementación funcional. 

Proyectos sin comunicación real sobre red. 

Proyectos que dependan de hardware obligatorio no disponible para el curso. 

Proyectos imposibles de reproducir en el entorno del grupo. 

Proyectos que realicen pruebas sobre infraestructura no autorizada. 

Página 4 de 8 

**Redes de Computadores** 

**Proyecto Final** 

## **9. Relación del proyecto con los laboratorios del curso** 

El proyecto final se apoya directamente en las actividades prácticas desarrolladas durante el semestre: 

- **Laboratorio 1.** Entregó herramientas para verificar conectividad, rutas, resolución de nombres y diagnóstico básico de red. 

- **Laboratorio 2.** Permitió preparar una máquina virtual o entorno reproducible para desarrollar y probar servicios. 

- **Laboratorio 3.** Entregó experiencia en captura e interpretación de tráfico con Wireshark sobre UDP y TCP. 

- **Laboratorio 4.** Entregó bases para observar exposición de puertos y servicios con Nmap, dentro de un entorno autorizado. 

**Conclusión.** Los laboratorios no son actividades aisladas: constituyen la base metodológica y técnica para que el grupo pueda construir, observar, analizar y defender su proyecto final. 

## **10. Hitos del proyecto** 

## **10.1. Hito 1: Propuesta de proyecto** 

Cada grupo deberá entregar una propuesta breve, cuya fecha será informada por el docente, que incluya: 

1. Título del proyecto. 

2. Integrantes del grupo. 

3. Variante temática elegida. 

4. Problema o necesidad a resolver. 

5. Arquitectura preliminar. 

6. Software a utilizar. 

7. Protocolo o forma de comunicación prevista. 

8. Componente de seguridad o confiabilidad prevista. 

## **10.2. Hito 2: Presentación semestral** 

De acuerdo con la planificación del curso, el proyecto contempla una **presentación semestral** en la fecha definida en el programa de la asignatura. 

En esta instancia, cada grupo deberá exponer: 

Problema y objetivos. 

Arquitectura del sistema. 

Decisiones tecnológicas adoptadas. 

Estado de avance. 

Dificultades principales. 

Plan de trabajo restante. 

Página 5 de 8 

**Redes de Computadores** 

**Proyecto Final** 

## **10.3. Hito 3: Entrega y presentación final** 

Cada grupo deberá realizar: 

Entrega final del informe. 

- Entrega del código fuente. 

- Entrega de instrucciones de ejecución. 

- Presentación final y defensa oral. 

**Demostración funcional del sistema.** 

## **11. Entregables finales obligatorios** 

Cada grupo deberá entregar: 

1. **Informe técnico en PDF.** 

2. **Código fuente completo.** 

3. **Instrucciones de ejecución.** 

4. **Diagrama de arquitectura.** 

5. **Evidencia de pruebas.** 

6. **Evidencia de análisis de red.** 

7. **Presentación final.** 

## **12. Estructura sugerida del informe** 

El informe final debería contener, como mínimo: 

1. Portada. 

2. Integrantes y roles. 

3. Resumen del proyecto. 

4. Problema y objetivos. 

5. Arquitectura del sistema. 

6. Tecnologías utilizadas. 

7. Diseño del flujo de comunicación o protocolo. 

8. Implementación. 

9. Seguridad o confiabilidad incorporada. 

10. Pruebas y validación. 

11. Análisis con Wireshark y, si corresponde, con Nmap. 

12. Limitaciones del sistema. 

13. Conclusiones. 

Página 6 de 8 

**Redes de Computadores** 

**Proyecto Final** 

## **13. Presentación final** 

La presentación final debe enfocarse en mostrar: 

El problema abordado. 

La arquitectura del sistema. 

La lógica de comunicación. 

La medida de seguridad o confiabilidad incorporada. 

- La evidencia de funcionamiento. 

La validación realizada. 

Las conclusiones principales. 

**Observación.** La presentación debe incluir una demostración funcional o evidencia clara y suficiente de que el sistema opera como fue descrito. 

## **14. Rúbrica de evaluación del proyecto final** 

|**Criterio**|**Ponderación**|
|---|---|
|Defnición del problema y objetivos.|10 %|
|Arquitectura del sistema.|15 %|
|Implementación funcional.|25 %|
|Diseño de comunicación o protocolo.|15 %|
|Seguridad o confabilidad incorporada.|10 %|
|Validación y análisis con herramientas del curso.|10 %|
|Informe técnico.|10 %|
|Presentación y defensa oral.|5 %|
|**Total.**|**100 %**|



## **14.1. Descripción de criterios** 

**Definición del problema y objetivos.** Se evaluará si el grupo delimita claramente qué resuelve su sistema, qué monitorea y por qué su propuesta tiene sentido técnico. 

**Arquitectura del sistema.** Se evaluará si la arquitectura es clara, coherente y correctamente representada, incluyendo nodos, servidor, flujo de comunicación y componentes principales. 

**Implementación funcional.** Se evaluará el funcionamiento real del sistema y el cumplimiento efectivo de los componentes mínimos exigidos. 

**Diseño de comunicación o protocolo.** Se evaluará si la elección de TCP, UDP, HTTP u otro mecanismo está justificada y correctamente implementada. 

**Seguridad o confiabilidad incorporada.** Se evaluará si la medida incorporada existe realmente, se comprende y se defiende técnicamente. 

**Validación y análisis con herramientas del curso.** Se evaluará la calidad del análisis realizado con Wireshark y, si corresponde, con Nmap, siempre sobre el entorno autorizado del grupo. 

**Informe técnico.** Se evaluará claridad, orden, redacción técnica, consistencia y calidad de la evidencia. 

Página 7 de 8 

**Redes de Computadores** 

**Proyecto Final** 

**Presentación y defensa oral.** Se evaluará claridad expositiva, dominio técnico, distribución razonable de participación y capacidad para responder preguntas. 

## **15. Recomendaciones para los grupos** 

Definan un alcance realista desde el principio. 

- Implementen primero la comunicación mínima y luego agreguen funcionalidades. 

- No sobrecarguen el proyecto con interfaz visual innecesaria si aún no logran comunicación estable. 

- Documenten desde temprano la arquitectura, los puertos y el flujo de mensajes. 

- Utilicen los laboratorios como apoyo directo para validar el proyecto. 

Prueben su sistema con tiempo antes de la presentación final. 

## **16. Observación final** 

El proyecto final no busca que el grupo construya un sistema industrial completo ni un producto comercial. El objetivo es que diseñe e implemente un prototipo funcional, técnicamente defendible y coherente con los contenidos del curso, demostrando integración real entre arquitectura de red, comunicación, seguridad básica y análisis técnico. 

Página 8 de 8 

