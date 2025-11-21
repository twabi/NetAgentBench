"""
LLM integration tests with REAL LLM providers (OpenAI, Gemini, Anthropic).

These tests require actual API keys and make real API calls.

IMPORTANT: 
- NO MOCKS - All tests use real LLM providers
- Tests are marked as @pytest.mark.manual and @pytest.mark.llm
- Tests are skipped if API keys are not available
- Tests make actual API calls (costs money)

To run these tests:
    pytest -m llm tests/integration/test_llm_integration.py

Prerequisites:
- Set API keys in .env file:
  - OPENAI_API_KEY=sk-...
  - GEMINI_API_KEY=...
  - ANTHROPIC_API_KEY=sk-...
"""
import pytest
import os
from pathlib import Path
from dotenv import load_dotenv
from benchmark.controller import BenchmarkController
from benchmark.task_repository import TaskRepository
from benchmark.property_executor import PropertyExecutor
from benchmark.llm.providers import OpenAIProvider, GeminiProvider, AnthropicProvider
from benchmark.llm.runner import LLMTestee
from benchmark.models.llm_config import LLMConfig


# Load environment variables
load_dotenv()


def get_api_key(env_var: str):
    """Get API key from environment."""
    return os.getenv(env_var)


# Check which providers are available
OPENAI_AVAILABLE = get_api_key("OPENAI_API_KEY") is not None
GEMINI_AVAILABLE = get_api_key("GEMINI_API_KEY") is not None
ANTHROPIC_AVAILABLE = get_api_key("ANTHROPIC_API_KEY") is not None


@pytest.mark.manual
@pytest.mark.llm
@pytest.mark.integration
@pytest.mark.skipif(not OPENAI_AVAILABLE, reason="OPENAI_API_KEY not set")
class TestOpenAIIntegration:
    """Test OpenAI provider integration with REAL API."""

    def test_openai_single_task_execution(self):
        """Test complete flow with real OpenAI API call."""
        # Setup
        repository = TaskRepository(Path("benchmark-tasks"))
        controller = BenchmarkController()  # REAL controller
        executor = PropertyExecutor(controller, repository)
        
        # Create OpenAI provider
        config = LLMConfig(
            provider="openai",
            model="gpt-4o-mini",  # Cheaper model for testing
            api_key=get_api_key("OPENAI_API_KEY"),
            temperature=0.7,
            max_tokens=1000
        )
        
        provider = OpenAIProvider(config)
        testee = LLMTestee(provider=provider, testee_id="openai_integration_test")
        
        # Run 1 reachability task with REAL OpenAI API
        print("\n⚠️  Making REAL OpenAI API call...")
        result = executor.run_property_tasks(
            property_type="reachability",
            submission_generator=lambda task: testee.generate_submission(task),
            limit=1
        )
        
        # Verify execution completed
        assert result.property_type == "reachability"
        assert result.total_tasks == 1
        assert len(result.results) == 1
        
        # Verify LLM generated something
        assert result.results[0].run_id is not None
        assert result.results[0].metrics.total_time > 0
        
        print(f"\n✅ OpenAI Test Results:")
        print(f"  Tasks completed: {result.total_tasks}")
        print(f"  Average score: {result.average_score:.3f}")
        print(f"  Successful: {result.successful_tasks}")

    def test_openai_response_parsing(self):
        """Test that OpenAI responses are parsed correctly."""
        repository = TaskRepository(Path("benchmark-tasks"))
        tasks = repository.load_tasks_by_property("reachability", limit=1)
        assert len(tasks) > 0
        task = tasks[0]
        
        # Create OpenAI testee
        config = LLMConfig(
            provider="openai",
            model="gpt-4o-mini",
            api_key=get_api_key("OPENAI_API_KEY"),
            temperature=0.7,
            max_tokens=1000
        )
        
        provider = OpenAIProvider(config)
        testee = LLMTestee(provider=provider, testee_id="openai_parse_test")
        
        # Generate submission
        print("\n⚠️  Making REAL OpenAI API call...")
        submission = testee.generate_submission(task)
        
        # Verify submission structure
        assert submission.task_id == task.task_id
        assert submission.testee_type == "llm"
        assert submission.approach is not None
        assert submission.approach.description is not None
        assert len(submission.approach.commands) > 0
        
        print(f"\n✅ OpenAI Response Parsed Successfully:")
        print(f"  Description: {submission.approach.description[:50]}...")
        print(f"  Commands for {len(submission.approach.commands)} nodes")


@pytest.mark.manual
@pytest.mark.llm
@pytest.mark.integration
@pytest.mark.skipif(not GEMINI_AVAILABLE, reason="GEMINI_API_KEY not set")
class TestGeminiIntegration:
    """Test Google Gemini provider integration with REAL API."""

    def test_gemini_single_task_execution(self):
        """Test complete flow with real Gemini API call."""
        # Setup
        repository = TaskRepository(Path("benchmark-tasks"))
        controller = BenchmarkController()  # REAL controller
        executor = PropertyExecutor(controller, repository)
        
        # Create Gemini provider
        config = LLMConfig(
            provider="gemini",
            model="gemini-1.5-flash",  # Faster model for testing
            api_key=get_api_key("GEMINI_API_KEY"),
            temperature=0.7,
            max_tokens=2000
        )
        
        provider = GeminiProvider(config)
        testee = LLMTestee(provider=provider, testee_id="gemini_integration_test")
        
        # Run 1 reachability task with REAL Gemini API
        print("\n⚠️  Making REAL Gemini API call...")
        result = executor.run_property_tasks(
            property_type="reachability",
            submission_generator=lambda task: testee.generate_submission(task),
            limit=1
        )
        
        # Verify execution completed
        assert result.property_type == "reachability"
        assert result.total_tasks == 1
        assert len(result.results) == 1
        
        # Verify LLM generated something
        assert result.results[0].run_id is not None
        assert result.results[0].metrics.total_time > 0
        
        print(f"\n✅ Gemini Test Results:")
        print(f"  Tasks completed: {result.total_tasks}")
        print(f"  Average score: {result.average_score:.3f}")
        print(f"  Successful: {result.successful_tasks}")

    def test_gemini_response_parsing(self):
        """Test that Gemini responses are parsed correctly."""
        repository = TaskRepository(Path("benchmark-tasks"))
        tasks = repository.load_tasks_by_property("reachability", limit=1)
        assert len(tasks) > 0
        task = tasks[0]
        
        # Create Gemini testee
        config = LLMConfig(
            provider="gemini",
            model="gemini-1.5-flash",
            api_key=get_api_key("GEMINI_API_KEY"),
            temperature=0.7,
            max_tokens=2000
        )
        
        provider = GeminiProvider(config)
        testee = LLMTestee(provider=provider, testee_id="gemini_parse_test")
        
        # Generate submission
        print("\n⚠️  Making REAL Gemini API call...")
        submission = testee.generate_submission(task)
        
        # Verify submission structure
        assert submission.task_id == task.task_id
        assert submission.testee_type == "llm"
        assert submission.approach is not None
        assert submission.approach.description is not None
        assert len(submission.approach.commands) > 0
        
        print(f"\n✅ Gemini Response Parsed Successfully:")
        print(f"  Description: {submission.approach.description[:50]}...")
        print(f"  Commands for {len(submission.approach.commands)} nodes")

    def test_gemini_provider_info(self):
        """Test Gemini provider returns correct info."""
        config = LLMConfig(
            provider="gemini",
            model="gemini-1.5-pro",
            api_key=get_api_key("GEMINI_API_KEY"),
            temperature=0.7,
            max_tokens=2000
        )
        
        provider = GeminiProvider(config)
        info = provider.get_model_info()
        
        assert info["provider"] == "gemini"
        assert info["model"] == "gemini-1.5-pro"
        assert info["temperature"] == 0.7
        assert info["max_tokens"] == 2000


@pytest.mark.manual
@pytest.mark.llm
@pytest.mark.integration
@pytest.mark.skipif(not ANTHROPIC_AVAILABLE, reason="ANTHROPIC_API_KEY not set")
class TestAnthropicIntegration:
    """Test Anthropic Claude provider integration with REAL API."""

    def test_anthropic_single_task_execution(self):
        """Test complete flow with real Anthropic API call."""
        # Setup
        repository = TaskRepository(Path("benchmark-tasks"))
        controller = BenchmarkController()  # REAL controller
        executor = PropertyExecutor(controller, repository)
        
        # Create Anthropic provider
        config = LLMConfig(
            provider="anthropic",
            model="claude-3-5-sonnet-20241022",
            api_key=get_api_key("ANTHROPIC_API_KEY"),
            temperature=0.7,
            max_tokens=2000
        )
        
        provider = AnthropicProvider(config)
        testee = LLMTestee(provider=provider, testee_id="anthropic_integration_test")
        
        # Run 1 reachability task with REAL Anthropic API
        print("\n⚠️  Making REAL Anthropic API call...")
        result = executor.run_property_tasks(
            property_type="reachability",
            submission_generator=lambda task: testee.generate_submission(task),
            limit=1
        )
        
        # Verify execution completed
        assert result.property_type == "reachability"
        assert result.total_tasks == 1
        assert len(result.results) == 1
        
        # Verify LLM generated something
        assert result.results[0].run_id is not None
        assert result.results[0].metrics.total_time > 0
        
        print(f"\n✅ Anthropic Test Results:")
        print(f"  Tasks completed: {result.total_tasks}")
        print(f"  Average score: {result.average_score:.3f}")
        print(f"  Successful: {result.successful_tasks}")


@pytest.mark.manual
@pytest.mark.llm
@pytest.mark.integration
class TestLLMErrorHandling:
    """Test LLM error handling scenarios."""

    def test_invalid_api_key_handling(self):
        """Test that invalid API key produces clear error."""
        config = LLMConfig(
            provider="openai",
            model="gpt-4o-mini",
            api_key="invalid_key_xyz",
            temperature=0.7,
            max_tokens=1000
        )
        
        provider = OpenAIProvider(config)
        testee = LLMTestee(provider=provider, testee_id="invalid_key_test")
        
        repository = TaskRepository(Path("benchmark-tasks"))
        tasks = repository.load_tasks_by_property("reachability", limit=1)
        assert len(tasks) > 0
        task = tasks[0]
        
        # Should raise clear error about authentication
        with pytest.raises(Exception) as exc_info:
            testee.generate_submission(task)
        
        error_str = str(exc_info.value).lower()
        assert "auth" in error_str or "api" in error_str or "key" in error_str or "401" in error_str

    @pytest.mark.skipif(not OPENAI_AVAILABLE, reason="OPENAI_API_KEY not set")
    def test_malformed_response_handling(self):
        """Test that system handles malformed LLM responses gracefully."""
        # This test is tricky - we'd need to mock the API response
        # In practice, the parser should handle various malformed responses
        # For now, we'll skip this as it requires mocking (which we avoid in integration tests)
        pytest.skip("Requires mocking LLM responses, which we avoid in integration tests")


@pytest.mark.manual
@pytest.mark.llm
@pytest.mark.integration
class TestMultiProviderComparison:
    """Test running same task with different LLM providers."""

    @pytest.mark.skipif(not (OPENAI_AVAILABLE and GEMINI_AVAILABLE), 
                        reason="Both OPENAI and GEMINI API keys required")
    def test_compare_openai_and_gemini(self):
        """Compare OpenAI and Gemini on the same task."""
        repository = TaskRepository(Path("benchmark-tasks"))
        controller = BenchmarkController()  # REAL controller
        
        tasks = repository.load_tasks_by_property("reachability", limit=1)
        assert len(tasks) > 0
        task = tasks[0]
        
        # Test with OpenAI
        print("\n⚠️  Making REAL OpenAI API call...")
        openai_config = LLMConfig(
            provider="openai",
            model="gpt-4o-mini",
            api_key=get_api_key("OPENAI_API_KEY"),
            temperature=0.7,
            max_tokens=1000
        )
        openai_provider = OpenAIProvider(openai_config)
        openai_testee = LLMTestee(provider=openai_provider, testee_id="openai_comparison")
        openai_submission = openai_testee.generate_submission(task)
        openai_result = controller.run(task, openai_submission)
        
        # Test with Gemini
        print("\n⚠️  Making REAL Gemini API call...")
        gemini_config = LLMConfig(
            provider="gemini",
            model="gemini-1.5-flash",
            api_key=get_api_key("GEMINI_API_KEY"),
            temperature=0.7,
            max_tokens=1000
        )
        gemini_provider = GeminiProvider(gemini_config)
        gemini_testee = LLMTestee(provider=gemini_provider, testee_id="gemini_comparison")
        gemini_submission = gemini_testee.generate_submission(task)
        gemini_result = controller.run(task, gemini_submission)
        
        # Both should complete
        assert openai_result.run_id is not None
        assert gemini_result.run_id is not None
        
        # Both should have valid scores
        assert 0.0 <= openai_result.scoring.final_score <= 1.0
        assert 0.0 <= gemini_result.scoring.final_score <= 1.0
        
        print(f"\n{'='*60}")
        print(f"Provider Comparison Results:")
        print(f"  OpenAI (gpt-4o-mini) score: {openai_result.scoring.final_score:.3f}")
        print(f"  Gemini (1.5-flash) score:   {gemini_result.scoring.final_score:.3f}")
        print(f"{'='*60}")

