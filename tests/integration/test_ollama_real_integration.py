import pytest
from pathlib import Path
from benchmark.controller import BenchmarkController
from benchmark.task_repository import TaskRepository
from benchmark.property_executor import PropertyExecutor
from benchmark.llm.providers import OllamaProvider
from benchmark.llm.runner import LLMTestee
from benchmark.models.llm_config import LLMConfig

@pytest.mark.manual
@pytest.mark.llm
@pytest.mark.integration
class TestOllamaIntegration:
    """Test Ollama provider integration with REAL API."""

    def test_ollama_connection(self):
        """Test direct connection to Ollama API."""
        config = LLMConfig(
            provider="ollama",
            model="gemma3:4b",
            base_url="http://10.23.52.8:11434",
            temperature=0.7,
            max_tokens=100
        )
        
        provider = OllamaProvider(config)
        
        # Direct call to generate_response
        print("\n⚠️  Making REAL Ollama API call (direct)...")
        response = provider.generate_response("Say hello in one word.")
        
        print(f"\n✅ Ollama Response: {response}")
        assert response is not None
        assert len(response) > 0

    def test_ollama_single_task_execution(self):
        """Test complete flow with real Ollama API call."""
        # Setup
        # Note: We assume benchmark-tasks directory exists in current working directory
        repository = TaskRepository(Path("benchmark-tasks"))
        controller = BenchmarkController()
        executor = PropertyExecutor(controller, repository)
        
        # Create Ollama provider
        config = LLMConfig(
            provider="ollama",
            model="gpt-oss:120b",
            base_url="http://10.23.52.8:11434",
            temperature=0.7,
            max_tokens=8192,
            timeout_seconds=900,
            provider_config={"num_ctx": 16384}
        )
        
        provider = OllamaProvider(config)
        testee = LLMTestee(provider=provider, testee_id="ollama_integration_test")
        
        # Run 1 reachability task
        print("\n⚠️  Making REAL Ollama API call (full task)...")
        result = executor.run_property_tasks(
            property_type="reachability",
            submission_generator=lambda task: testee.generate_submission(task),
            limit=1
        )
        
        print(result)
        
        # Verify execution completed
        assert result.property_type == "reachability"
        assert result.total_tasks == 1
        assert len(result.results) == 1
        
        # Verify LLM generated something
        assert result.results[0].run_id is not None
        
        print(f"\n✅ Ollama Test Results:")
        print(f"  Tasks completed: {result.total_tasks}")
        print(f"  Average score: {result.average_score:.3f}")
        print(f"  Successful: {result.successful_tasks}")
