#!/usr/bin/env python3
"""
Test script to check if arXiv search is working
"""

import sys
import os
import logging
sys.path.append(os.path.join(os.path.dirname(__file__), "."))

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from shared.arxiv_parser import ArxivParser
from datetime import datetime, timedelta

def test_search():
    """Test arXiv search functionality"""
    print("🔍 Testing arXiv search...")
    logger.info("Starting arXiv search test")
    
    try:
        parser = ArxivParser()
        logger.info("ArxivParser initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize ArxivParser: {e}")
        logger.error(f"Failed to initialize ArxivParser: {e}")
        return
    
    # Test 1: Basic search
    print("\n1. Testing basic search for 'AI'...")
    try:
        papers = parser.search_papers("AI", max_results=5)
        print(f"✅ Found {len(papers)} papers")
        logger.info(f"Found {len(papers)} papers for query 'AI'")
        for i, paper in enumerate(papers[:3]):
            print(f"   {i+1}. {paper.title[:60]}...")
    except Exception as e:
        print(f"❌ Error in basic search: {e}")
        logger.error(f"Error in basic search: {e}")
    
    # Test 2: Search with date filter
    print("\n2. Testing search with date filter...")
    try:
        date_from = datetime.now() - timedelta(days=7)
        papers = parser.search_papers("machine learning", max_results=5, date_from=date_from)
        print(f"✅ Found {len(papers)} papers from last 7 days")
        logger.info(f"Found {len(papers)} papers for 'machine learning' from last 7 days")
        for i, paper in enumerate(papers[:3]):
            print(f"   {i+1}. {paper.title[:60]}...")
    except Exception as e:
        print(f"❌ Error in date-filtered search: {e}")
        logger.error(f"Error in date-filtered search: {e}")
    
    # Test 3: Search by category
    print("\n3. Testing search by category...")
    try:
        papers = parser.search_papers("transformer", max_results=5, categories=["cs.AI", "cs.LG"])
        print(f"✅ Found {len(papers)} papers in AI/LG categories")
        logger.info(f"Found {len(papers)} papers for 'transformer' in AI/LG categories")
        for i, paper in enumerate(papers[:3]):
            print(f"   {i+1}. {paper.title[:60]}...")
    except Exception as e:
        print(f"❌ Error in category search: {e}")
        logger.error(f"Error in category search: {e}")

if __name__ == "__main__":
    print("Starting test...")
    test_search()
    print("Test completed.") 