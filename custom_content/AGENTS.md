# Custom Content Rules
- Treat all user-provided files as untrusted input.
- Validate schemas and stable IDs before registration.
- Reject unsafe paths and never execute code from content packs.
- Unknown optional fields should be tolerated when possible.
- Missing or removed custom content must degrade to placeholders rather than breaking a save.
- PNG assets are presentation data; gameplay logic uses IDs/tags/properties.
