"""Test script for verifying real Groq generation."""

from pydantic import BaseModel

from app.llm.groq import GroqLLM


class SampleVerification(BaseModel):
    message: str
    venue_type: str


def main():
    llm = GroqLLM()
    print("Testing generate_json with Groq model:", llm.model_name)
    result = llm.generate_json(
        system="You are a helpful event planner assistant.",
        prompt="Suggest a venue type and greeting for a modern rooftop party.",
        schema=SampleVerification,
    )
    print("Structured result:", result)
    print("Metadata:", llm.last_metadata)

    print("\nTesting generate_text:")
    text = llm.generate_text(
        system="You are a helpful event planner assistant.",
        prompt="Write a one-sentence tagline for EventGenie.",
    )
    print("Text result:", text)
    print("Metadata:", llm.last_metadata)


if __name__ == "__main__":
    main()
