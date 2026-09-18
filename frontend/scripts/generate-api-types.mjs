import { readFile, writeFile } from 'node:fs/promises'
import { resolve } from 'node:path'

const openApiFile = process.env.OPENAPI_FILE
const openApiUrl = process.env.OPENAPI_URL ?? 'http://localhost:8000/openapi.json'
const document = openApiFile
  ? JSON.parse(await readFile(resolve(openApiFile), 'utf8'))
  : await fetch(openApiUrl).then(async (response) => {
      if (!response.ok) {
        throw new Error(`OpenAPI indisponível: ${response.status}`)
      }
      return response.json()
    })

const schemas = document.components?.schemas ?? {}

function typeName(reference) {
  return `ApiSchemas[${JSON.stringify(reference.split('/').pop())}]`
}

function schemaType(schema) {
  if (!schema) return 'unknown'
  if (schema.type === 'null') return 'null'
  if (schema.$ref) return typeName(schema.$ref)
  if (schema.enum) return schema.enum.map((value) => JSON.stringify(value)).join(' | ') || 'never'
  if (schema.anyOf || schema.oneOf) {
    return (schema.anyOf ?? schema.oneOf).map(schemaType).join(' | ')
  }
  if (schema.allOf) return schema.allOf.map(schemaType).join(' & ')
  if (schema.type === 'array') return `Array<${schemaType(schema.items)}>`
  if (schema.type === 'object' || schema.properties) {
    const properties = schema.properties ?? {}
    const required = new Set(schema.required ?? [])
    const entries = Object.entries(properties).map(([name, value]) => {
      const key = /^[A-Za-z_$][\w$]*$/.test(name) ? name : JSON.stringify(name)
      const optional = required.has(name) ? '' : '?'
      return `    ${key}${optional}: ${schemaType(value)};`
    })
    if (schema.additionalProperties) {
      entries.push('    [key: string]: unknown;')
    }
    return entries.length ? `{\n${entries.join('\n')}\n  }` : 'Record<string, unknown>'
  }
  if (schema.type === 'integer' || schema.type === 'number') return 'number'
  if (schema.type === 'boolean') return 'boolean'
  if (schema.type === 'string') return 'string'
  return 'unknown'
}

const lines = [
  '/* Generated from the FastAPI OpenAPI document. Do not edit manually. */',
  'export type ApiSchemas = {',
]
for (const [name, schema] of Object.entries(schemas)) {
  lines.push(`  ${name}: ${schemaType(schema)};`)
}
lines.push('}', '')

await writeFile(resolve('src/types/api.generated.ts'), `${lines.join('\n')}\n`, 'utf8')
console.log(`Generated ${Object.keys(schemas).length} OpenAPI schemas.`)
