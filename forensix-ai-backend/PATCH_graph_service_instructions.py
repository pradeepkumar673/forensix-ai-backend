"""
PATCH FILE: app/services/graph_service.py
==========================================
Apply these TWO changes to fix the 422 graph error.

The problem: _llm_extract_entities_chunk() and _llm_graph_merge() both call
_call_ollama() directly with model='llama3' which isn't installed.

FIX: Replace them with calls to get_llm_response() (which auto-falls back to Groq).

=== CHANGE 1: Add this import at the top of graph_service.py ===
Add this line AFTER the existing imports (after `from app.core.config import get_settings`):

    from app.services.llm_service import get_llm_response

=== CHANGE 2: Replace _llm_extract_entities_chunk() ===

FIND this function (around line 6852):

    async def _llm_extract_entities_chunk(
        source_text: str,
        model: str,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
        prompt = _EXTRACT_ENTITIES_PROMPT.format(text=source_text)
        response_text, inference_ms = await _call_ollama(
            prompt=prompt,
            model=model,
            system=_GRAPH_SYSTEM_PROMPT,
            temperature=0.05,
            max_tokens=5000,
        )
        try:
            parsed = _extract_json_block(response_text)
        except (json.JSONDecodeError, ValueError) as exc:
            logger.error("Entity extraction JSON parse failure: %s", exc)
            raise ValueError(
                f"LLM did not return valid JSON for entity extraction.\\n"
                f"Raw response (first 400 chars):\\n{response_text[:400]}"
            ) from exc
        entities = parsed.get("entities", [])
        relationships = parsed.get("relationships", [])
        return entities, relationships, inference_ms

REPLACE WITH:

    async def _llm_extract_entities_chunk(
        source_text: str,
        model: str,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
        import time as _time
        prompt = _EXTRACT_ENTITIES_PROMPT.format(text=source_text)
        t0 = _time.perf_counter()
        resp = await get_llm_response(
            prompt=prompt,
            system_prompt=_GRAPH_SYSTEM_PROMPT,
            temperature=0.05,
            max_tokens=5000,
            provider="auto",
        )
        inference_ms = round((_time.perf_counter() - t0) * 1000)
        response_text = resp.get("response", "")
        try:
            parsed = _extract_json_block(response_text)
        except (json.JSONDecodeError, ValueError) as exc:
            logger.error("Entity extraction JSON parse failure: %s", exc)
            raise ValueError(
                f"LLM did not return valid JSON for entity extraction.\\n"
                f"Raw response (first 400 chars):\\n{response_text[:400]}"
            ) from exc
        entities = parsed.get("entities", [])
        relationships = parsed.get("relationships", [])
        return entities, relationships, inference_ms

=== CHANGE 3: Replace _llm_graph_merge inside build_entity_graph() ===

FIND this nested function (around line 6973):

        async def _llm_graph_merge(m: str) -> tuple[dict[str, Any], int]:
            response_text, inference_ms = await _call_ollama(
                prompt=prompt,
                model=m,
                system=_GRAPH_SYSTEM_PROMPT,
                temperature=0.05,
                max_tokens=6000,
            )
            try:
                parsed = _extract_json_block(response_text)
            except (json.JSONDecodeError, ValueError) as exc:
                logger.error("Graph build JSON parse failure: %s", exc)
                raise ValueError(
                    f"LLM did not return valid JSON for graph construction.\\n"
                    f"Raw response (first 400 chars):\\n{response_text[:400]}"
                ) from exc
            return parsed, inference_ms

REPLACE WITH:

        async def _llm_graph_merge(m: str) -> tuple[dict[str, Any], int]:
            import time as _time
            t0 = _time.perf_counter()
            resp = await get_llm_response(
                prompt=prompt,
                system_prompt=_GRAPH_SYSTEM_PROMPT,
                temperature=0.05,
                max_tokens=6000,
                provider="auto",
            )
            inference_ms = round((_time.perf_counter() - t0) * 1000)
            response_text = resp.get("response", "")
            try:
                parsed = _extract_json_block(response_text)
            except (json.JSONDecodeError, ValueError) as exc:
                logger.error("Graph build JSON parse failure: %s", exc)
                raise ValueError(
                    f"LLM did not return valid JSON for graph construction.\\n"
                    f"Raw response (first 400 chars):\\n{response_text[:400]}"
                ) from exc
            return parsed, inference_ms
"""
