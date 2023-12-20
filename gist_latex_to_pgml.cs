// This Clipboard Fusion macro makes it easy to copy Latex from the Learning Standards Project into WebWork compatible formats

using System;
using System.Collections.Generic;
using System.Text.RegularExpressions;

// The 'text' parameter will contain the text from the:
//   - Current Clipboard when run by HotKey
//   - History Item when run from the History Menu
// The returned string will be:
//   - Placed directly on the Clipboard when run as a Macro
//   - Ignored by ClipboardFusion if it is 'null'
//   - Passed along to the next action in a Trigger (null changed to an empty string)
public static class ClipboardFusionHelper
{
	static string ReplaceMathSymbols(string input)
    {
        // Regular expression to match pairs of $ symbols
        string pattern = @"\$([^$]+)\$";
        string replacement = @"\($1\)";
        string result = Regex.Replace(input, pattern, replacement);
        return result;
    }
	
	static string RemoveMathcite(string input)	
	{
		input = Regex.Replace(input, @"\\MathCite\{[a-zA-Z0-9]+\}\[([^\]]+)\]", @"$1");
		input = Regex.Replace(input, @"\\MathCite\{([a-zA-Z0-9]+)\}[^\[]", @"$1");
		return input;
	}
	
	static string OtherReplacements(string input)
	{
		input = input.Replace(@"\bbR", @"\mathbb{R}");
		input = input.Replace(@"\spn", @"\text{span}");
		input = input.Replace(@"\image", @"\text{im}");
		return input;
	}
	
	public static string ProcessText(string text)
	{
		// your code goes here
		text = ReplaceMathSymbols(text);
		text = RemoveMathcite(text);
		text = OtherReplacements(text);
        text = "$BR $BR $BR $BBOLD LS: $EBOLD\r\n" + text;
		return text;
	}
}
