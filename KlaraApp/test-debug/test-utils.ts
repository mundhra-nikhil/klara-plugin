/**
 * Test utilities for debugging Word text replacement issues
 *
 * This file contains helper functions for testing and debugging
 * text replacement functionality, especially with special characters.
 */

import {
  searchAndSelect,
  highlightRange,
  clearHighlights,
  replaceText,
  replaceTextInParagraph,
  testWordApiAvailability
} from '../src/taskpane/word-context';

/**
 * Test case structure
 */
interface TestCase {
  name: string;
  description: string;
  originalText: string;
  replacementText: string;
  paragraphIndex?: number;
  expectedResult: 'success' | 'fail' | 'manual';
}

/**
 * Test results structure
 */
interface TestResult {
  testCase: TestCase;
  success: boolean;
  error?: string;
  duration: number;
  timestamp: string;
}

/**
 * Run a single test case
 */
export async function runTestCase(testCase: TestCase): Promise<TestResult> {
  const startTime = Date.now();
  console.log(`\n🧪 Test: ${testCase.name}`);
  console.log(`📝 Description: ${testCase.description}`);
  console.log(`🔤 Original: "${testCase.originalText}"`);
  console.log(`✏️ Replacement: "${testCase.replacementText}"`);

  try {
    if (testCase.paragraphIndex !== undefined) {
      console.log(`📍 Paragraph Index: ${testCase.paragraphIndex}`);
      await replaceTextInParagraph(
        testCase.originalText,
        testCase.replacementText,
        testCase.paragraphIndex
      );
    } else {
      await replaceText(testCase.originalText, testCase.replacementText, 0);
    }

    const duration = Date.now() - startTime;
    console.log(`✅ Test passed in ${duration}ms`);

    return {
      testCase,
      success: true,
      duration,
      timestamp: new Date().toISOString()
    };
  } catch (error: any) {
    const duration = Date.now() - startTime;
    console.error(`❌ Test failed in ${duration}ms:`, error.message);

    return {
      testCase,
      success: false,
      error: error.message,
      duration,
      timestamp: new Date().toISOString()
    };
  }
}

/**
 * Run multiple test cases
 */
export async function runTestSuite(testCases: TestCase[]): Promise<TestResult[]> {
  console.log(`\n🚀 Starting test suite with ${testCases.length} test cases`);

  const results: TestResult[] = [];

  for (const testCase of testCases) {
    const result = await runTestCase(testCase);
    results.push(result);

    // Small delay between tests
    await new Promise(resolve => setTimeout(resolve, 500));
  }

  const summary = generateTestSummary(results);
  console.log(`\n📊 Test Summary:\n${summary}`);

  return results;
}

/**
 * Generate test summary
 */
function generateTestSummary(results: TestResult[]): string {
  const passed = results.filter(r => r.success).length;
  const failed = results.filter(r => !r.success).length;
  const totalTime = results.reduce((sum, r) => sum + r.duration, 0);

  let summary = `Total Tests: ${results.length}\n`;
  summary += `✅ Passed: ${passed}\n`;
  summary += `❌ Failed: ${failed}\n`;
  summary += `⏱️ Total Time: ${totalTime}ms\n`;
  summary += `⚡ Average Time: ${Math.round(totalTime / results.length)}ms\n`;

  if (failed > 0) {
    summary += `\n❌ Failed Tests:\n`;
    results
      .filter(r => !r.success)
      .forEach(r => {
        summary += `  - ${r.testCase.name}: ${r.error}\n`;
      });
  }

  return summary;
}

/**
 * Predefined test cases for special characters
 */
export const specialCharacterTests: TestCase[] = [
  {
    name: 'Section Symbol Spacing',
    description: 'Section symbol should have space after it',
    originalText: '§1234',
    replacementText: '§ 1234',
    expectedResult: 'success'
  },
  {
    name: 'Copyright Symbol',
    description: 'Copyright symbol text replacement',
    originalText: 'Copyright 2024',
    replacementText: '© 2024',
    expectedResult: 'success'
  },
  {
    name: 'Registered Trademark',
    description: 'Registered trademark symbol',
    originalText: 'Microsoft Registered',
    replacementText: 'Microsoft®',
    expectedResult: 'success'
  },
  {
    name: 'Trademark Symbol',
    description: 'Trademark symbol replacement',
    originalText: 'Klara Trademark',
    replacementText: 'Klara™',
    expectedResult: 'success'
  }
];

/**
 * Test Word API availability and basic functionality
 */
export async function testWordApi(): Promise<boolean> {
  console.log('\n🔍 Testing Word API availability...');

  const result = await testWordApiAvailability();

  if (result.available) {
    console.log('✅ Word API is available');
    if (result.documentInfo) {
      console.log('📄 Document Info:', result.documentInfo);
    }
    return true;
  } else {
    console.error('❌ Word API not available:', result.error);
    return false;
  }
}

/**
 * Debug helper: Show paragraph content
 */
export async function debugParagraphContent(paragraphIndex: number): Promise<void> {
  console.log(`\n🔍 Debugging paragraph ${paragraphIndex}...`);

  try {
    await Word.run(async (context) => {
      const paragraphs = context.document.body.paragraphs;
      paragraphs.load('items');
      await context.sync();

      if (paragraphIndex >= 0 && paragraphIndex < paragraphs.items.length) {
        const paragraph = paragraphs.items[paragraphIndex];
        paragraph.load('text');
        await context.sync();

        console.log(`📋 Paragraph ${paragraphIndex} content:`);
        console.log(`"${paragraph.text}"`);
        console.log(`Length: ${paragraph.text?.length || 0} characters`);
      } else {
        console.error(`❌ Invalid paragraph index: ${paragraphIndex}`);
      }
    });
  } catch (error: any) {
    console.error('❌ Error debugging paragraph:', error.message);
  }
}

/**
 * Create test document with special characters
 */
export async function createTestDocument(): Promise<void> {
  console.log('📄 Creating test document...');

  try {
    await Word.run(async (context) => {
      const body = context.document.body;
      body.clear();
      await context.sync();

      // Add test content with special characters
      const testContent = [
        'Test Document for Klara Word Add-in',
        '',
        'Special Character Tests:',
        '§1234 should be § 1234',
        'Copyright 2024 should be © 2024',
        'Microsoft Registered should be Microsoft®',
        'Klara Trademark should be Klara™',
        '',
        'Number Formatting Tests:',
        '1. First item',
        '2. Second item',
        '3. Third item',
        '',
        'End of test document'
      ];

      for (const line of testContent) {
        body.insertParagraph(line, 'End');
      }

      await context.sync();
      console.log('✅ Test document created successfully');
    });
  } catch (error: any) {
    console.error('❌ Error creating test document:', error.message);
  }
}

// Export functions for use in browser console
if (typeof window !== 'undefined') {
  (window as any).KlaraTestUtils = {
    runTestCase,
    runTestSuite,
    specialCharacterTests,
    testWordApi,
    debugParagraphContent,
    createTestDocument
  };
  console.log('🧪 Klara Test Utils loaded! Use KlaraTestUtils in console.');
}