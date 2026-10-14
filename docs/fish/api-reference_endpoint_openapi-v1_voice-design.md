> ## Documentation Index
> Fetch the complete documentation index at: https://docs.fish.audio/llms.txt
> Use this file to discover all available pages before exploring further.

# Voice Design

> Generate candidate voices from a prompt

<Warning>
  This endpoint only accepts `application/json`.

  You must include the `model: voice-design-1` header. Extra request fields are rejected.
</Warning>

<Note>
  A successful request returns generated voice candidates with `audio_base64`
  audio payloads. Decode the base64 value to write the candidate audio to a
  file.
</Note>

## Example

```bash theme={null}
curl --request POST https://api.fish.audio/v1/voice-design \
  --header "Authorization: Bearer $FISH_API_KEY" \
  --header "Content-Type: application/json" \
  --header "model: voice-design-1" \
  --data '{
    "instruction": "Warm, confident studio narrator with a natural tone",
    "reference_text": "Welcome to Fish Audio.",
    "language": "en",
    "n": 2,
    "speed": 1,
    "num_step": 32,
    "guidance_scale": 2,
    "instruct_guidance_scale": 0,
    "seed": 42
  }'
```

## Usage notes

* `instruction` is required and must be 1 to 2000 characters.
* `reference_text` is optional preview text and can be up to 150 characters.
* `n` controls how many candidates are returned. The supported range is 1 to 4.
* `seed` is optional and can help reproduce candidate generation.
* The endpoint is stateless: it does not create batches, samples, voice models, or presigned URLs.
* Billing happens once per successful generation request, not once per candidate.


## OpenAPI

````yaml post /v1/voice-design
openapi: 3.1.0
info:
  title: FishAudio OpenAPI
  version: '1'
servers:
  - description: Fish Audio API
    url: https://api.fish.audio
security: []
tags: []
paths:
  /v1/voice-design:
    post:
      tags:
        - OpenAPI v1
      summary: Voice Design
      parameters:
        - in: header
          name: model
          description: Specify which voice-design model to use.
          required: true
          schema:
            const: voice-design-1
            default: voice-design-1
            title: Model
            type: string
          deprecated: false
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/VoiceDesignRequest'
      responses:
        '200':
          description: Request fulfilled, document follows
          headers: {}
          content:
            application/json:
              schema:
                properties:
                  candidates:
                    description: Generated voice candidates.
                    items:
                      $ref: '#/components/schemas/VoiceDesignCandidate'
                    title: Candidates
                    type: array
                required:
                  - candidates
                type: object
        '401':
          description: No permission -- see authorization schemes
          headers: {}
          content:
            application/json:
              schema:
                properties:
                  status:
                    title: Status
                    type: integer
                  message:
                    title: Message
                    type: string
                  reason:
                    anyOf:
                      - type: string
                      - type: 'null'
                    default: null
                    title: Reason
                required:
                  - status
                  - message
                type: object
        '402':
          description: No payment -- see charging schemes
          headers: {}
          content:
            application/json:
              schema:
                properties:
                  status:
                    title: Status
                    type: integer
                  message:
                    title: Message
                    type: string
                  reason:
                    anyOf:
                      - type: string
                      - type: 'null'
                    default: null
                    title: Reason
                required:
                  - status
                  - message
                type: object
        '503':
          description: The server cannot process the request due to a high load
          headers: {}
          content:
            application/json:
              schema:
                properties:
                  status:
                    title: Status
                    type: integer
                  message:
                    title: Message
                    type: string
                  reason:
                    anyOf:
                      - type: string
                      - type: 'null'
                    default: null
                    title: Reason
                required:
                  - status
                  - message
                type: object
      security:
        - BearerAuth: []
      x-codeSamples:
        - lang: bash
          label: Voice Design
          source: |-
            curl --request POST \
              --url https://api.fish.audio/v1/voice-design \
              --header 'Authorization: Bearer <token>' \
              --header 'Content-Type: application/json' \
              --header 'model: voice-design-1' \
              --data '{
                "instruction": "Warm, confident studio narrator with a natural tone",
                "reference_text": "Welcome to Fish Audio.",
                "language": "en",
                "n": 2,
                "speed": 1,
                "num_step": 32,
                "guidance_scale": 2,
                "instruct_guidance_scale": 0,
                "seed": 42
              }'
components:
  schemas:
    VoiceDesignRequest:
      additionalProperties: false
      description: >-
        Request body for synchronous voice design generation. The endpoint
        returns generated voice candidates with base64-encoded audio.
      examples:
        - guidance_scale: 2
          instruct_guidance_scale: 0
          instruction: Warm, confident studio narrator with a natural tone
          language: en
          'n': 2
          num_step: 32
          reference_text: Welcome to Fish Audio.
          seed: 42
          speed: 1
      properties:
        instruction:
          description: Voice design prompt. Must contain 1 to 2000 characters.
          maxLength: 2000
          minLength: 1
          title: Instruction
          type: string
        reference_text:
          anyOf:
            - maxLength: 150
              type: string
            - type: 'null'
          default: null
          description: Optional text used as reference content for the generated voice.
          title: Reference Text
        language:
          anyOf:
            - type: string
            - type: 'null'
          default: null
          description: Optional BCP-47 language hint, such as `en`, `zh`, or `ja`.
          title: Language
        'n':
          default: 2
          description: Number of voice candidates to generate.
          maximum: 4
          minimum: 1
          title: 'N'
          type: integer
        speed:
          default: 1
          description: Speaking speed multiplier for candidate generation.
          exclusiveMinimum: 0
          maximum: 3
          title: Speed
          type: number
        num_step:
          default: 32
          description: Number of diffusion steps used by the voice-design model.
          maximum: 128
          minimum: 1
          title: Num Step
          type: integer
        guidance_scale:
          default: 2
          description: >-
            Classifier-free guidance scale. Higher values follow the prompt more
            strongly.
          minimum: 0
          title: Guidance Scale
          type: number
        instruct_guidance_scale:
          default: 0
          description: Instruction guidance scale for prompt conditioning.
          minimum: 0
          title: Instruct Guidance Scale
          type: number
        seed:
          anyOf:
            - type: integer
            - type: 'null'
          default: null
          description: Optional deterministic seed for candidate generation.
          title: Seed
      required:
        - instruction
      title: VoiceDesignRequest
      type: object
    VoiceDesignCandidate:
      properties:
        id:
          description: Stable candidate identifier.
          title: Id
          type: string
        index:
          description: Candidate index in this response.
          minimum: 0
          title: Index
          type: integer
        audio_base64:
          description: Base64 encoded generated audio.
          title: Audio Base64
          type: string
        sample_rate:
          description: Audio sample rate in Hz.
          exclusiveMinimum: 0
          title: Sample Rate
          type: integer
        duration_ms:
          description: Audio duration in milliseconds.
          minimum: 0
          title: Duration Ms
          type: integer
        text:
          anyOf:
            - type: string
            - type: 'null'
          default: null
          description: Preview text associated with this generated voice, when available.
          title: Text
        instruct:
          anyOf:
            - type: string
            - type: 'null'
          default: null
          description: Instruction text associated with this candidate, when available.
          title: Instruct
        language:
          anyOf:
            - type: string
            - type: 'null'
          default: null
          description: Detected or requested candidate language, when available.
          title: Language
      required:
        - id
        - index
        - audio_base64
        - sample_rate
        - duration_ms
      title: VoiceDesignCandidate
      type: object
  securitySchemes:
    BearerAuth:
      type: http
      scheme: bearer

````

This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.