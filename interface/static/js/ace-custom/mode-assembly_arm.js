define("ace/mode/assembly_arm_highlight_rules",["require","exports","module","ace/lib/oop","ace/mode/text_highlight_rules"], function(require, exports, module) {
"use strict";

var oop = require("../lib/oop");
var TextHighlightRules = require("./text_highlight_rules").TextHighlightRules;

var AssemblyARMHighlightRules = function() {

    this.$rules = { start: 
       [ { token: 'keyword.control.assembly',
           regex: '\\b(?:and|andeq|andne|andcs|andcc|andmi|andpl|andvs|andvc|andhi|andls|andge|andlt|andgt|andle|andal|eor|eoreq|eorne|eorcs|eorcc|eormi|eorpl|eorvs|eorvc|eorhi|eorls|eorge|eorlt|eorgt|eorle|eoral|sub|subeq|subne|subcs|subcc|submi|subpl|subvs|subvc|subhi|subls|subge|sublt|subgt|suble|subal|rsb|rsbeq|rsbne|rsbcs|rsbcc|rsbmi|rsbpl|rsbvs|rsbvc|rsbhi|rsbls|rsbge|rsblt|rsbgt|rsble|rsbal|add|addeq|addne|addcs|addcc|addmi|addpl|addvs|addvc|addhi|addls|addge|addlt|addgt|addle|addal|adc|adceq|adcne|adccs|adccc|adcmi|adcpl|adcvs|adcvc|adchi|adcls|adcge|adclt|adcgt|adcle|adcal|sbc|sbceq|sbcne|sbccs|sbccc|sbcmi|sbcpl|sbcvs|sbcvc|sbchi|sbcls|sbcge|sbclt|sbcgt|sbcle|sbcal|rsc|rsceq|rscne|rsccs|rsccc|rscmi|rscpl|rscvs|rscvc|rschi|rscls|rscge|rsclt|rscgt|rscle|rscal|tst|tsteq|tstne|tstcs|tstcc|tstmi|tstpl|tstvs|tstvc|tsthi|tstls|tstge|tstlt|tstgt|tstle|tstal|teq|teqeq|teqne|teqcs|teqcc|teqmi|teqpl|teqvs|teqvc|teqhi|teqls|teqge|teqlt|teqgt|teqle|teqal|cmp|cmpeq|cmpne|cmpcs|cmpcc|cmpmi|cmppl|cmpvs|cmpvc|cmphi|cmpls|cmpge|cmplt|cmpgt|cmple|cmpal|cmn|cmneq|cmnne|cmncs|cmncc|cmnmi|cmnpl|cmnvs|cmnvc|cmnhi|cmnls|cmnge|cmnlt|cmngt|cmnle|cmnal|orr|orreq|orrne|orrcs|orrcc|orrmi|orrpl|orrvs|orrvc|orrhi|orrls|orrge|orrlt|orrgt|orrle|orral|mov|moveq|movne|movcs|movcc|movmi|movpl|movvs|movvc|movhi|movls|movge|movlt|movgt|movle|moval|bic|biceq|bicne|biccs|biccc|bicmi|bicpl|bicvs|bicvc|bichi|bicls|bicge|biclt|bicgt|bicle|bical|mvn|mvneq|mvnne|mvncs|mvncc|mvnmi|mvnpl|mvnvs|mvnvc|mvnhi|mvnls|mvnge|mvnlt|mvngt|mvnle|mvnal|lsr|lsreq|lsrne|lsrcs|lsrcc|lsrmi|lsrpl|lsrvs|lsrvc|lsrhi|lsrls|lsrge|lsrlt|lsrgt|lsrle|lsral|lsl|lsleq|lslne|lslcs|lslcc|lslmi|lslpl|lslvs|lslvc|lslhi|lslls|lslge|lsllt|lslgt|lslle|lslal|asr|asreq|asrne|asrcs|asrcc|asrmi|asrpl|asrvs|asrvc|asrhi|asrls|asrge|asrlt|asrgt|asrle|asral|ror|roreq|rorne|rorcs|rorcc|rormi|rorpl|rorvs|rorvc|rorhi|rorls|rorge|rorlt|rorgt|rorle|roral|rrx|rrxeq|rrxne|rrxcs|rrxcc|rrxmi|rrxpl|rrxvs|rrxvc|rrxhi|rrxls|rrxge|rrxlt|rrxgt|rrxle|rrxal|mrs|mrseq|mrsne|mrscs|mrscc|mrsmi|mrspl|mrsvs|mrsvc|mrshi|mrsls|mrsge|mrslt|mrsgt|mrsle|mrsal|msr|msreq|msrne|msrcs|msrcc|msrmi|msrpl|msrvs|msrvc|msrhi|msrls|msrge|msrlt|msrgt|msrle|msral|ldr|ldreq|ldrne|ldrcs|ldrcc|ldrmi|ldrpl|ldrvs|ldrvc|ldrhi|ldrls|ldrge|ldrlt|ldrgt|ldrle|ldral|str|streq|strne|strcs|strcc|strmi|strpl|strvs|strvc|strhi|strls|strge|strlt|strgt|strle|stral|ldm|ldmeq|ldmne|ldmcs|ldmcc|ldmmi|ldmpl|ldmvs|ldmvc|ldmhi|ldmls|ldmge|ldmlt|ldmgt|ldmle|ldmal|stm|stmeq|stmne|stmcs|stmcc|stmmi|stmpl|stmvs|stmvc|stmhi|stmls|stmge|stmlt|stmgt|stmle|stmal|push|pusheq|pushne|pushcs|pushcc|pushmi|pushpl|pushvs|pushvc|pushhi|pushls|pushge|pushlt|pushgt|pushle|pushal|pop|popeq|popne|popcs|popcc|popmi|poppl|popvs|popvc|pophi|popls|popge|poplt|popgt|pople|popal|b|beq|bne|bcs|bcc|bmi|bpl|bvs|bvc|bhi|bls|bge|blt|bgt|ble|bal|bx|bxeq|bxne|bxcs|bxcc|bxmi|bxpl|bxvs|bxvc|bxhi|bxls|bxge|bxlt|bxgt|bxle|bxal|bl|bleq|blne|blcs|blcc|blmi|blpl|blvs|blvc|blhi|blls|blge|bllt|blgt|blle|blal|blx|blxeq|blxne|blxcs|blxcc|blxmi|blxpl|blxvs|blxvc|blxhi|blxls|blxge|blxlt|blxgt|blxle|blxal|mul|muleq|mulne|mulcs|mulcc|mulmi|mulpl|mulvs|mulvc|mulhi|mulls|mulge|mullt|mulgt|mulle|mulal|mla|mlaeq|mlane|mlacs|mlacc|mlami|mlapl|mlavs|mlavc|mlahi|mlals|mlage|mlalt|mlagt|mlale|mlaal|swp|swpeq|swpne|swpcs|swpcc|swpmi|swppl|swpvs|swpvc|swphi|swpls|swpge|swplt|swpgt|swple|swpal|swi|swieq|swine|swics|swicc|swimi|swipl|swivs|swivc|swihi|swils|swige|swilt|swigt|swile|swial|svc|svceq|svcne|svccs|svccc|svcmi|svcpl|svcvs|svcvc|svchi|svcls|svcge|svclt|svcgt|svcle|svcal|nop|nopeq|nopne|nopcs|nopcc|nopmi|noppl|nopvs|nopvc|nophi|nopls|nopge|noplt|nopgt|nople|nopal|ldmed|ldmedeq|ldmedne|ldmedcs|ldmedcc|ldmedmi|ldmedpl|ldmedvs|ldmedvc|ldmedhi|ldmedls|ldmedge|ldmedlt|ldmedgt|ldmedle|ldmedal|ldmib|ldmibeq|ldmibne|ldmibcs|ldmibcc|ldmibmi|ldmibpl|ldmibvs|ldmibvc|ldmibhi|ldmibls|ldmibge|ldmiblt|ldmibgt|ldmible|ldmibal|ldmfd|ldmfdeq|ldmfdne|ldmfdcs|ldmfdcc|ldmfdmi|ldmfdpl|ldmfdvs|ldmfdvc|ldmfdhi|ldmfdls|ldmfdge|ldmfdlt|ldmfdgt|ldmfdle|ldmfdal|ldmia|ldmiaeq|ldmiane|ldmiacs|ldmiacc|ldmiami|ldmiapl|ldmiavs|ldmiavc|ldmiahi|ldmials|ldmiage|ldmialt|ldmiagt|ldmiale|ldmiaal|ldmea|ldmeaeq|ldmeane|ldmeacs|ldmeacc|ldmeami|ldmeapl|ldmeavs|ldmeavc|ldmeahi|ldmeals|ldmeage|ldmealt|ldmeagt|ldmeale|ldmeaal|ldmdb|ldmdbeq|ldmdbne|ldmdbcs|ldmdbcc|ldmdbmi|ldmdbpl|ldmdbvs|ldmdbvc|ldmdbhi|ldmdbls|ldmdbge|ldmdblt|ldmdbgt|ldmdble|ldmdbal|ldmfa|ldmfaeq|ldmfane|ldmfacs|ldmfacc|ldmfami|ldmfapl|ldmfavs|ldmfavc|ldmfahi|ldmfals|ldmfage|ldmfalt|ldmfagt|ldmfale|ldmfaal|ldmda|ldmdaeq|ldmdane|ldmdacs|ldmdacc|ldmdami|ldmdapl|ldmdavs|ldmdavc|ldmdahi|ldmdals|ldmdage|ldmdalt|ldmdagt|ldmdale|ldmdaal|stmfa|stmfaeq|stmfane|stmfacs|stmfacc|stmfami|stmfapl|stmfavs|stmfavc|stmfahi|stmfals|stmfage|stmfalt|stmfagt|stmfale|stmfaal|stmib|stmibeq|stmibne|stmibcs|stmibcc|stmibmi|stmibpl|stmibvs|stmibvc|stmibhi|stmibls|stmibge|stmiblt|stmibgt|stmible|stmibal|stmea|stmeaeq|stmeane|stmeacs|stmeacc|stmeami|stmeapl|stmeavs|stmeavc|stmeahi|stmeals|stmeage|stmealt|stmeagt|stmeale|stmeaal|stmia|stmiaeq|stmiane|stmiacs|stmiacc|stmiami|stmiapl|stmiavs|stmiavc|stmiahi|stmials|stmiage|stmialt|stmiagt|stmiale|stmiaal|stmfd|stmfdeq|stmfdne|stmfdcs|stmfdcc|stmfdmi|stmfdpl|stmfdvs|stmfdvc|stmfdhi|stmfdls|stmfdge|stmfdlt|stmfdgt|stmfdle|stmfdal|stmdb|stmdbeq|stmdbne|stmdbcs|stmdbcc|stmdbmi|stmdbpl|stmdbvs|stmdbvc|stmdbhi|stmdbls|stmdbge|stmdblt|stmdbgt|stmdble|stmdbal|stmed|stmedeq|stmedne|stmedcs|stmedcc|stmedmi|stmedpl|stmedvs|stmedvc|stmedhi|stmedls|stmedge|stmedlt|stmedgt|stmedle|stmedal|stmda|stmdaeq|stmdane|stmdacs|stmdacc|stmdami|stmdapl|stmdavs|stmdavc|stmdahi|stmdals|stmdage|stmdalt|stmdagt|stmdale|stmdaal|strb|strbeq|strbne|strbcs|strbcc|strbmi|strbpl|strbvs|strbvc|strbhi|strbls|strbge|strblt|strbgt|strble|strbal|ldrb|ldrbeq|ldrbne|ldrbcs|ldrbcc|ldrbmi|ldrbpl|ldrbvs|ldrbvc|ldrbhi|ldrbls|ldrbge|ldrblt|ldrbgt|ldrble|ldrbal|ands|andseq|andsne|andscs|andscc|andsmi|andspl|andsvs|andsvc|andshi|andsls|andsge|andslt|andsgt|andsle|andsal|eors|eorseq|eorsne|eorscs|eorscc|eorsmi|eorspl|eorsvs|eorsvc|eorshi|eorsls|eorsge|eorslt|eorsgt|eorsle|eorsal|subs|subseq|subsne|subscs|subscc|subsmi|subspl|subsvs|subsvc|subshi|subsls|subsge|subslt|subsgt|subsle|subsal|rsbs|rsbseq|rsbsne|rsbscs|rsbscc|rsbsmi|rsbspl|rsbsvs|rsbsvc|rsbshi|rsbsls|rsbsge|rsbslt|rsbsgt|rsbsle|rsbsal|adds|addseq|addsne|addscs|addscc|addsmi|addspl|addsvs|addsvc|addshi|addsls|addsge|addslt|addsgt|addsle|addsal|adcs|adcseq|adcsne|adcscs|adcscc|adcsmi|adcspl|adcsvs|adcsvc|adcshi|adcsls|adcsge|adcslt|adcsgt|adcsle|adcsal|sbcs|sbcseq|sbcsne|sbcscs|sbcscc|sbcsmi|sbcspl|sbcsvs|sbcsvc|sbcshi|sbcsls|sbcsge|sbcslt|sbcsgt|sbcsle|sbcsal|rscs|rscseq|rscsne|rscscs|rscscc|rscsmi|rscspl|rscsvs|rscsvc|rscshi|rscsls|rscsge|rscslt|rscsgt|rscsle|rscsal|tsts|tstseq|tstsne|tstscs|tstscc|tstsmi|tstspl|tstsvs|tstsvc|tstshi|tstsls|tstsge|tstslt|tstsgt|tstsle|tstsal|teqs|teqseq|teqsne|teqscs|teqscc|teqsmi|teqspl|teqsvs|teqsvc|teqshi|teqsls|teqsge|teqslt|teqsgt|teqsle|teqsal|cmps|cmpseq|cmpsne|cmpscs|cmpscc|cmpsmi|cmpspl|cmpsvs|cmpsvc|cmpshi|cmpsls|cmpsge|cmpslt|cmpsgt|cmpsle|cmpsal|cmns|cmnseq|cmnsne|cmnscs|cmnscc|cmnsmi|cmnspl|cmnsvs|cmnsvc|cmnshi|cmnsls|cmnsge|cmnslt|cmnsgt|cmnsle|cmnsal|orrs|orrseq|orrsne|orrscs|orrscc|orrsmi|orrspl|orrsvs|orrsvc|orrshi|orrsls|orrsge|orrslt|orrsgt|orrsle|orrsal|movs|movseq|movsne|movscs|movscc|movsmi|movspl|movsvs|movsvc|movshi|movsls|movsge|movslt|movsgt|movsle|movsal|bics|bicseq|bicsne|bicscs|bicscc|bicsmi|bicspl|bicsvs|bicsvc|bicshi|bicsls|bicsge|bicslt|bicsgt|bicsle|bicsal|mvns|mvnseq|mvnsne|mvnscs|mvnscc|mvnsmi|mvnspl|mvnsvs|mvnsvc|mvnshi|mvnsls|mvnsge|mvnslt|mvnsgt|mvnsle|mvnsal)\\b',
           caseInsensitive: true },
         { token: 'asmcomment.assembly',
           regex: ';.*$' },
         { token: 'variable.parameter.register.assembly',
           regex: '\\b(?:r[0-9]|r1[0-5]|sl|fp|ip|sp|lr|pc|cpsr|spsr)\\b',
           caseInsensitive: true },
         { token: 'sectiontitle.assembly',
           regex: 'SECTION\\s(?:INTVEC|CODE|DATA)' },
         { token: 'memdeclare.assembly',
           regex: '\\bD[CS](?:8|16|32)\\b' },
         { token: 'constant.character.assembly',
           regex: '#-?0x[0-9a-fA-F]+' },
           { token: 'constant.character.assembly',
           regex: '#-?[0-9]+' },
         { token: 'label.assembly',
           regex: '^[ \t]*[a-zA-Z0-9_]*' }
    ] }

    this.normalizeRules();
};

AssemblyARMHighlightRules.metaData = { fileTypes: [ 's' ],
      name: 'Assembly arm',
      scopeName: 'source.assembly' };


oop.inherits(AssemblyARMHighlightRules, TextHighlightRules);

exports.AssemblyARMHighlightRules = AssemblyARMHighlightRules;
});

define("ace/mode/folding/coffee",["require","exports","module","ace/lib/oop","ace/mode/folding/fold_mode","ace/range"], function(require, exports, module) {
"use strict";

var oop = require("../../lib/oop");
var BaseFoldMode = require("./fold_mode").FoldMode;
var Range = require("../../range").Range;

var FoldMode = exports.FoldMode = function() {};
oop.inherits(FoldMode, BaseFoldMode);

(function() {

    this.getFoldWidgetRange = function(session, foldStyle, row) {
        var range = this.indentationBlock(session, row);
        if (range)
            return range;

        var re = /\S/;
        var line = session.getLine(row);
        var startLevel = line.search(re);
        if (startLevel == -1 || line[startLevel] != "#")
            return;

        var startColumn = line.length;
        var maxRow = session.getLength();
        var startRow = row;
        var endRow = row;

        while (++row < maxRow) {
            line = session.getLine(row);
            var level = line.search(re);

            if (level == -1)
                continue;

            if (line[level] != "#")
                break;

            endRow = row;
        }

        if (endRow > startRow) {
            var endColumn = session.getLine(endRow).length;
            return new Range(startRow, startColumn, endRow, endColumn);
        }
    };
    this.getFoldWidget = function(session, foldStyle, row) {
        var line = session.getLine(row);
        var indent = line.search(/\S/);
        var next = session.getLine(row + 1);
        var prev = session.getLine(row - 1);
        var prevIndent = prev.search(/\S/);
        var nextIndent = next.search(/\S/);

        if (indent == -1) {
            session.foldWidgets[row - 1] = prevIndent!= -1 && prevIndent < nextIndent ? "start" : "";
            return "";
        }
        if (prevIndent == -1) {
            if (indent == nextIndent && line[indent] == "#" && next[indent] == "#") {
                session.foldWidgets[row - 1] = "";
                session.foldWidgets[row + 1] = "";
                return "start";
            }
        } else if (prevIndent == indent && line[indent] == "#" && prev[indent] == "#") {
            if (session.getLine(row - 2).search(/\S/) == -1) {
                session.foldWidgets[row - 1] = "start";
                session.foldWidgets[row + 1] = "";
                return "";
            }
        }

        if (prevIndent!= -1 && prevIndent < indent)
            session.foldWidgets[row - 1] = "start";
        else
            session.foldWidgets[row - 1] = "";

        if (indent < nextIndent)
            return "start";
        else
            return "";
    };

}).call(FoldMode.prototype);

});

define("ace/mode/assembly_arm",["require","exports","module","ace/lib/oop","ace/mode/text","ace/mode/assembly_arm_highlight_rules","ace/mode/folding/coffee"], function(require, exports, module) {
"use strict";

var oop = require("../lib/oop");
var TextMode = require("./text").Mode;
var AssemblyARMHighlightRules = require("./assembly_arm_highlight_rules").AssemblyARMHighlightRules;
var FoldMode = require("./folding/coffee").FoldMode;

var Mode = function() {
    this.HighlightRules = AssemblyARMHighlightRules;
    this.foldingRules = new FoldMode();
};
oop.inherits(Mode, TextMode);

(function() {
    this.lineCommentStart = ";";
    this.$id = "ace/mode/assembly_arm";
}).call(Mode.prototype);

exports.Mode = Mode;
});
