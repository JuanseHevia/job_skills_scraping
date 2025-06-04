import asyncio
import json
import os
from openai import AsyncOpenAI
from typing import List, Dict, Any, Optional

# Con esta línea nos aseguramos de que las variables de entorno se carguen correctamente
# principalmente la OPENAI_API_KEY que nos permite autenticar con la API de OpenAI.
import dotenv
dotenv.load_dotenv(dotenv_path=dotenv.find_dotenv())

client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

async def extract_skills_from_job_posting(
    job_posting_html: str,
    model: str = "gpt-3.5-turbo", # Puedes usar o4-mini también, que es barato y puede dar mejores resultados
    temperature: float = 0.0,
    max_retries: int = 3,
    retry_delay: int = 5
) -> Optional[Dict[str, Any]]:
    """
    Función asíncrona para extraer habilidades de un job posting utilizando la API de OpenAI.

    Args:
        job_posting_html (str): El contenido HTML del job posting.
        model (str): El nombre del modelo de OpenAI a utilizar.
        temperature (float): La temperatura para la generación del modelo.
        max_retries (int): Número máximo de reintentos en caso de errores de la API.
        retry_delay (int): Tiempo de espera en segundos entre reintentos.

    Returns:
        Optional[Dict[str, Any]]: Un diccionario con las habilidades extraídas o None si falla.
    """
    prompt = f"""
    Eres un experto analista de datos y recursos humanos. Tu tarea es extraer información
    específica de la siguiente descripción de puesto de trabajo.
    Por favor, analiza el siguiente texto y extrae las siguientes variables en formato JSON:
    - "habilidades_tecnicas": Una lista de las habilidades técnicas clave mencionadas.
    - "habilidades_blandas": Una lista de las habilidades blandas o "soft skills" requeridas.
    - "experiencia_requerida_años": El número de años de experiencia requeridos (si se menciona, de lo contrario null). Si es un rango (ej. "3-5 años"), devuelve el valor más bajo (3). Si dice "más de X años", devuelve X.
    - "tipo_contrato": El tipo de contrato (ej. "Full-time", "Part-time", "Contrato", "Freelance", "Indefinido", "Temporal", etc. si se especifica, de lo contrario null).

    El output debe ser estrictamente un objeto JSON válido, sin ningún texto adicional antes o después.

    ---
    Descripción del Puesto de Trabajo:
    {job_posting_html}
    ---
    """

    messages = [
        {"role": "system", "content": "You are a helpful assistant designed to output JSON."},
        {"role": "user", "content": prompt}
    ]

    for attempt in range(max_retries):
        try:
            chat_completion = await client.chat.completions.create(
                model=model,
                messages=messages,  # type: ignore
                temperature=temperature,
                response_format={"type": "json_object"} # Importante para asegurar JSON
            )
            response_content: Optional[str] = chat_completion.choices[0].message.content
            # Intentar parsear el JSON. A veces los LLMs pueden incluir texto extra.
            try:
                extracted_data = json.loads(response_content) if response_content else {}
                return extracted_data
            except json.JSONDecodeError:
                print(f"Advertencia: La respuesta no es un JSON válido en el intento {attempt + 1}: {response_content}...")
                # Intentar limpiar la respuesta si es un JSON malformado
                # Esto es una estrategia heurística y no siempre funcionará
                if isinstance(response_content, str) and response_content.startswith("```json") and response_content.endswith("```"):
                    try:
                        extracted_data = json.loads(response_content[7:-3].strip())
                        return extracted_data
                    except json.JSONDecodeError:
                        pass # Falló la limpieza, se adelanta al siguiente intento
        except Exception as e:
            print(f"Error en la llamada a la API (intento {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
            else:
                print(f"Fallaron todos los reintentos para el job posting. Error final: {e}")
    return None

async def process_job_postings_async(
    input_filepath: str,
    output_filepath: str,
    model: str = "gpt-3.5-turbo",
    temperature: float = 0.0,
    max_concurrent_requests: int = 5 # Límite de concurrencia para evitar Rate Limits
) -> List[Dict[str, Any]]:
    """
    Procesa un archivo JSON de job postings de forma asíncrona para extraer habilidades.

    Args:
        input_filepath (str): Ruta al archivo JSON de entrada con los job postings.
        output_filepath (str): Ruta al archivo JSON donde se guardarán los resultados.
        model (str): Modelo de OpenAI a utilizar.
        temperature (float): Temperatura para la generación del modelo.
        max_concurrent_requests (int): Número máximo de llamadas concurrentes a la API.

    Returns:
        List[Dict[str, Any]]: Una lista de diccionarios con la información original
                               y las habilidades extraídas.
    """
    if not os.path.exists(input_filepath):
        print(f"Error: El archivo de entrada no existe en {input_filepath}")
        return []

    with open(input_filepath, 'r', encoding='utf-8') as f:
        job_postings_data = json.load(f)

    extracted_results = []
    
    # Usar un Semaphore para limitar las peticiones concurrentes
    semaphore = asyncio.Semaphore(max_concurrent_requests)

    async def bounded_extract(job_posting: Dict[str, Any]):
        async with semaphore:
            # Asumiendo que cada job posting tiene una clave 'html_content' o similar
            # basada en el proyecto job_skills_scraping.
            # Puedes ajustar esto según la estructura real de tu JSON.
            html_content = job_posting.get('html_content', job_posting.get('job_description', ''))
            
            # Si el contenido es muy largo, puedes truncarlo o resumirlo
            # para ahorrar tokens y evitar límites de contexto del modelo.
            # Aquí, por simplicidad, se envía todo el contenido.
            
            extracted_info = await extract_skills_from_job_posting(
                job_posting_html=html_content,
                model=model,
                temperature=temperature
            )
            
            # Combina la información original con la extraída
            result = job_posting.copy()
            result['extracted_skills'] = extracted_info
            return result

    tasks = []
    for job_posting in job_postings_data:
        tasks.append(bounded_extract(job_posting))
    
    # Ejecuta todas las tareas concurrentemente y espera sus resultados
    extracted_results = await asyncio.gather(*tasks)

    # Guarda los resultados en un nuevo archivo JSON
    with open(output_filepath, 'w', encoding='utf-8') as f:
        json.dump(extracted_results, f, indent=4, ensure_ascii=False)
    
    print(f"Extracción completada. Resultados guardados en {output_filepath}")
    return extracted_results

# Ejemplo de cómo se usaría en un script principal o en el notebook del taller:
# (Esto iría fuera de utils.py, en el notebook o en un script de ejecución)
"""
import asyncio
from utils import process_job_postings_async
import os

async def main():
    # Configura tu API Key (o asegura que esté en tus variables de entorno)
    # os.environ["OPENAI_API_KEY"] = "tu_api_key_aqui" # NO RECOMENDADO EN PRODUCCIÓN

    input_file = "job_postings_raw.json" # Asume que tienes un archivo JSON de entrada
    output_file = "job_postings_extracted_skills.json"

    # Crea un archivo JSON de ejemplo para testing si no lo tienes
    if not os.path.exists(input_file):
        print(f"Creando archivo de ejemplo: {input_file}")
        example_data = [
            {
                "id": "1",
                "title": "Analista de Datos Jr.",
                "html_content": "Buscamos un Analista de Datos Junior con al menos 2 años de experiencia en Python y SQL. Se valorará conocimiento de Power BI. Habilidades blandas: comunicación efectiva y proactividad. Contrato full-time."
            },
            {
                "id": "2",
                "title": "Desarrollador Senior Python",
                "html_content": "Ingeniero de Software Senior con más de 5 años de experiencia en desarrollo Python, Django y AWS. Experiencia en metodologías ágiles. Se requiere liderazgo de equipo y resolución de problemas. Contrato indefinido."
            },
            {
                "id": "3",
                "title": "Científico de Datos",
                "html_content": "Necesitamos un Científico de Datos con al menos 3 años de experiencia. Fuertes habilidades en Machine Learning (TensorFlow, PyTorch) y estadística. Capacidad para trabajar en equipo y pensamiento crítico. Posición a tiempo completo."
            }
        ]
        with open(input_file, 'w', encoding='utf-8') as f:
            json.dump(example_data, f, indent=4, ensure_ascii=False)
        print(f"Archivo de ejemplo {input_file} creado.")

    extracted_data = await process_job_postings_async(
        input_filepath=input_file,
        output_filepath=output_file,
        model="gpt-3.5-turbo", # O el modelo que prefieras y tengas acceso
        max_concurrent_requests=3 # Ajustar según los límites de la API y el rendimiento deseado
    )

    print("\nPrimeras 2 entradas extraídas:")
    for item in extracted_data[:2]:
        print(json.dumps(item, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    # Para ejecutar código asíncrono en un script
    asyncio.run(main())

    # Si estás en un Jupyter Notebook, usa:
    # await main()
"""