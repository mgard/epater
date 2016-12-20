define("ace/mode/assembly_arm_highlight_rules",["require","exports","module","ace/lib/oop","ace/mode/text_highlight_rules"], function(require, exports, module) {
"use strict";

var oop = require("../lib/oop");
var TextHighlightRules = require("./text_highlight_rules").TextHighlightRules;

var AssemblyARMHighlightRules = function() {

    this.$rules = { start: 
       [ { token: 'keyword.control.assembly',
          regex: '\\b(?:stm|stmvs|stmcc|stmne|stmcs|stmgt|stmpl|stmls|stmal|stmmi|stmhi|stmlt|stmeq|stmle|stmvc|stmge|lsl|lslvs|lslcc|lslne|lslcs|lslgt|lslpl|lslls|lslal|lslmi|lslhi|lsllt|lsleq|lslle|lslvc|lslge|lsr|lsrvs|lsrcc|lsrne|lsrcs|lsrgt|lsrpl|lsrls|lsral|lsrmi|lsrhi|lsrlt|lsreq|lsrle|lsrvc|lsrge|swp|swpvs|swpcc|swpne|swpcs|swpgt|swppl|swpls|swpal|swpmi|swphi|swplt|swpeq|swple|swpvc|swpge|bic|bicvs|biccc|bicne|biccs|bicgt|bicpl|bicls|bical|bicmi|bichi|biclt|biceq|bicle|bicvc|bicge|str|strvs|strcc|strne|strcs|strgt|strpl|strls|stral|strmi|strhi|strlt|streq|strle|strvc|strge|msr|msrvs|msrcc|msrne|msrcs|msrgt|msrpl|msrls|msral|msrmi|msrhi|msrlt|msreq|msrle|msrvc|msrge|tst|tstvs|tstcc|tstne|tstcs|tstgt|tstpl|tstls|tstal|tstmi|tsthi|tstlt|tsteq|tstle|tstvc|tstge|bl|blvs|blcc|blne|blcs|blgt|blpl|blls|blal|blmi|blhi|bllt|bleq|blle|blvc|blge|ldm|ldmvs|ldmcc|ldmne|ldmcs|ldmgt|ldmpl|ldmls|ldmal|ldmmi|ldmhi|ldmlt|ldmeq|ldmle|ldmvc|ldmge|pop|popvs|popcc|popne|popcs|popgt|poppl|popls|popal|popmi|pophi|poplt|popeq|pople|popvc|popge|mrs|mrsvs|mrscc|mrsne|mrscs|mrsgt|mrspl|mrsls|mrsal|mrsmi|mrshi|mrslt|mrseq|mrsle|mrsvc|mrsge|cmp|cmpvs|cmpcc|cmpne|cmpcs|cmpgt|cmppl|cmpls|cmpal|cmpmi|cmphi|cmplt|cmpeq|cmple|cmpvc|cmpge|sbc|sbcvs|sbccc|sbcne|sbccs|sbcgt|sbcpl|sbcls|sbcal|sbcmi|sbchi|sbclt|sbceq|sbcle|sbcvc|sbcge|svc|svcvs|svccc|svcne|svccs|svcgt|svcpl|svcls|svcal|svcmi|svchi|svclt|svceq|svcle|svcvc|svcge|mla|mlavs|mlacc|mlane|mlacs|mlagt|mlapl|mlals|mlaal|mlami|mlahi|mlalt|mlaeq|mlale|mlavc|mlage|orr|orrvs|orrcc|orrne|orrcs|orrgt|orrpl|orrls|orral|orrmi|orrhi|orrlt|orreq|orrle|orrvc|orrge|ror|rorvs|rorcc|rorne|rorcs|rorgt|rorpl|rorls|roral|rormi|rorhi|rorlt|roreq|rorle|rorvc|rorge|rsc|rscvs|rsccc|rscne|rsccs|rscgt|rscpl|rscls|rscal|rscmi|rschi|rsclt|rsceq|rscle|rscvc|rscge|adc|adcvs|adccc|adcne|adccs|adcgt|adcpl|adcls|adcal|adcmi|adchi|adclt|adceq|adcle|adcvc|adcge|b|bvs|bcc|bne|bcs|bgt|bpl|bls|bal|bmi|bhi|blt|beq|ble|bvc|bge|asr|asrvs|asrcc|asrne|asrcs|asrgt|asrpl|asrls|asral|asrmi|asrhi|asrlt|asreq|asrle|asrvc|asrge|add|addvs|addcc|addne|addcs|addgt|addpl|addls|addal|addmi|addhi|addlt|addeq|addle|addvc|addge|mov|movvs|movcc|movne|movcs|movgt|movpl|movls|moval|movmi|movhi|movlt|moveq|movle|movvc|movge|mvn|mvnvs|mvncc|mvnne|mvncs|mvngt|mvnpl|mvnls|mvnal|mvnmi|mvnhi|mvnlt|mvneq|mvnle|mvnvc|mvnge|push|pushvs|pushcc|pushne|pushcs|pushgt|pushpl|pushls|pushal|pushmi|pushhi|pushlt|pusheq|pushle|pushvc|pushge|rsb|rsbvs|rsbcc|rsbne|rsbcs|rsbgt|rsbpl|rsbls|rsbal|rsbmi|rsbhi|rsblt|rsbeq|rsble|rsbvc|rsbge|ldr|ldrvs|ldrcc|ldrne|ldrcs|ldrgt|ldrpl|ldrls|ldral|ldrmi|ldrhi|ldrlt|ldreq|ldrle|ldrvc|ldrge|teq|teqvs|teqcc|teqne|teqcs|teqgt|teqpl|teqls|teqal|teqmi|teqhi|teqlt|teqeq|teqle|teqvc|teqge|blx|blxvs|blxcc|blxne|blxcs|blxgt|blxpl|blxls|blxal|blxmi|blxhi|blxlt|blxeq|blxle|blxvc|blxge|bx|bxvs|bxcc|bxne|bxcs|bxgt|bxpl|bxls|bxal|bxmi|bxhi|bxlt|bxeq|bxle|bxvc|bxge|and|andvs|andcc|andne|andcs|andgt|andpl|andls|andal|andmi|andhi|andlt|andeq|andle|andvc|andge|rrx|rrxvs|rrxcc|rrxne|rrxcs|rrxgt|rrxpl|rrxls|rrxal|rrxmi|rrxhi|rrxlt|rrxeq|rrxle|rrxvc|rrxge|swi|swivs|swicc|swine|swics|swigt|swipl|swils|swial|swimi|swihi|swilt|swieq|swile|swivc|swige|eor|eorvs|eorcc|eorne|eorcs|eorgt|eorpl|eorls|eoral|eormi|eorhi|eorlt|eoreq|eorle|eorvc|eorge|mul|mulvs|mulcc|mulne|mulcs|mulgt|mulpl|mulls|mulal|mulmi|mulhi|mullt|muleq|mulle|mulvc|mulge|sub|subvs|subcc|subne|subcs|subgt|subpl|subls|subal|submi|subhi|sublt|subeq|suble|subvc|subge|cmn|cmnvs|cmncc|cmnne|cmncs|cmngt|cmnpl|cmnls|cmnal|cmnmi|cmnhi|cmnlt|cmneq|cmnle|cmnvc|cmnge|lia|liavs|liacc|liane|liacs|liagt|liapl|lials|liaal|liami|liahi|lialt|liaeq|liale|liavc|liage|led|ledvs|ledcc|ledne|ledcs|ledgt|ledpl|ledls|ledal|ledmi|ledhi|ledlt|ledeq|ledle|ledvc|ledge|lea|leavs|leacc|leane|leacs|leagt|leapl|leals|leaal|leami|leahi|lealt|leaeq|leale|leavc|leage|lfd|lfdvs|lfdcc|lfdne|lfdcs|lfdgt|lfdpl|lfdls|lfdal|lfdmi|lfdhi|lfdlt|lfdeq|lfdle|lfdvc|lfdge|lda|ldavs|ldacc|ldane|ldacs|ldagt|ldapl|ldals|ldaal|ldami|ldahi|ldalt|ldaeq|ldale|ldavc|ldage|ldb|ldbvs|ldbcc|ldbne|ldbcs|ldbgt|ldbpl|ldbls|ldbal|ldbmi|ldbhi|ldblt|ldbeq|ldble|ldbvc|ldbge|lib|libvs|libcc|libne|libcs|libgt|libpl|libls|libal|libmi|libhi|liblt|libeq|lible|libvc|libge|lfa|lfavs|lfacc|lfane|lfacs|lfagt|lfapl|lfals|lfaal|lfami|lfahi|lfalt|lfaeq|lfale|lfavc|lfage|dia|diavs|diacc|diane|diacs|diagt|diapl|dials|diaal|diami|diahi|dialt|diaeq|diale|diavc|diage|ded|dedvs|dedcc|dedne|dedcs|dedgt|dedpl|dedls|dedal|dedmi|dedhi|dedlt|dedeq|dedle|dedvc|dedge|dea|deavs|deacc|deane|deacs|deagt|deapl|deals|deaal|deami|deahi|dealt|deaeq|deale|deavc|deage|dfd|dfdvs|dfdcc|dfdne|dfdcs|dfdgt|dfdpl|dfdls|dfdal|dfdmi|dfdhi|dfdlt|dfdeq|dfdle|dfdvc|dfdge|dda|ddavs|ddacc|ddane|ddacs|ddagt|ddapl|ddals|ddaal|ddami|ddahi|ddalt|ddaeq|ddale|ddavc|ddage|ddb|ddbvs|ddbcc|ddbne|ddbcs|ddbgt|ddbpl|ddbls|ddbal|ddbmi|ddbhi|ddblt|ddbeq|ddble|ddbvc|ddbge|dib|dibvs|dibcc|dibne|dibcs|dibgt|dibpl|dibls|dibal|dibmi|dibhi|diblt|dibeq|dible|dibvc|dibge|dfa|dfavs|dfacc|dfane|dfacs|dfagt|dfapl|dfals|dfaal|dfami|dfahi|dfalt|dfaeq|dfale|dfavc|dfage|mia|miavs|miacc|miane|miacs|miagt|miapl|mials|miaal|miami|miahi|mialt|miaeq|miale|miavc|miage|med|medvs|medcc|medne|medcs|medgt|medpl|medls|medal|medmi|medhi|medlt|medeq|medle|medvc|medge|mea|meavs|meacc|meane|meacs|meagt|meapl|meals|meaal|meami|meahi|mealt|meaeq|meale|meavc|meage|mfd|mfdvs|mfdcc|mfdne|mfdcs|mfdgt|mfdpl|mfdls|mfdal|mfdmi|mfdhi|mfdlt|mfdeq|mfdle|mfdvc|mfdge|mda|mdavs|mdacc|mdane|mdacs|mdagt|mdapl|mdals|mdaal|mdami|mdahi|mdalt|mdaeq|mdale|mdavc|mdage|mdb|mdbvs|mdbcc|mdbne|mdbcs|mdbgt|mdbpl|mdbls|mdbal|mdbmi|mdbhi|mdblt|mdbeq|mdble|mdbvc|mdbge|mib|mibvs|mibcc|mibne|mibcs|mibgt|mibpl|mibls|mibal|mibmi|mibhi|miblt|mibeq|mible|mibvc|mibge|mfa|mfavs|mfacc|mfane|mfacs|mfagt|mfapl|mfals|mfaal|mfami|mfahi|mfalt|mfaeq|mfale|mfavc|mfage|sia|siavs|siacc|siane|siacs|siagt|siapl|sials|siaal|siami|siahi|sialt|siaeq|siale|siavc|siage|sed|sedvs|sedcc|sedne|sedcs|sedgt|sedpl|sedls|sedal|sedmi|sedhi|sedlt|sedeq|sedle|sedvc|sedge|sea|seavs|seacc|seane|seacs|seagt|seapl|seals|seaal|seami|seahi|sealt|seaeq|seale|seavc|seage|sfd|sfdvs|sfdcc|sfdne|sfdcs|sfdgt|sfdpl|sfdls|sfdal|sfdmi|sfdhi|sfdlt|sfdeq|sfdle|sfdvc|sfdge|sda|sdavs|sdacc|sdane|sdacs|sdagt|sdapl|sdals|sdaal|sdami|sdahi|sdalt|sdaeq|sdale|sdavc|sdage|sdb|sdbvs|sdbcc|sdbne|sdbcs|sdbgt|sdbpl|sdbls|sdbal|sdbmi|sdbhi|sdblt|sdbeq|sdble|sdbvc|sdbge|sib|sibvs|sibcc|sibne|sibcs|sibgt|sibpl|sibls|sibal|sibmi|sibhi|siblt|sibeq|sible|sibvc|sibge|sfa|sfavs|sfacc|sfane|sfacs|sfagt|sfapl|sfals|sfaal|sfami|sfahi|sfalt|sfaeq|sfale|sfavc|sfage|tia|tiavs|tiacc|tiane|tiacs|tiagt|tiapl|tials|tiaal|tiami|tiahi|tialt|tiaeq|tiale|tiavc|tiage|ted|tedvs|tedcc|tedne|tedcs|tedgt|tedpl|tedls|tedal|tedmi|tedhi|tedlt|tedeq|tedle|tedvc|tedge|tea|teavs|teacc|teane|teacs|teagt|teapl|teals|teaal|teami|teahi|tealt|teaeq|teale|teavc|teage|tfd|tfdvs|tfdcc|tfdne|tfdcs|tfdgt|tfdpl|tfdls|tfdal|tfdmi|tfdhi|tfdlt|tfdeq|tfdle|tfdvc|tfdge|tda|tdavs|tdacc|tdane|tdacs|tdagt|tdapl|tdals|tdaal|tdami|tdahi|tdalt|tdaeq|tdale|tdavc|tdage|tdb|tdbvs|tdbcc|tdbne|tdbcs|tdbgt|tdbpl|tdbls|tdbal|tdbmi|tdbhi|tdblt|tdbeq|tdble|tdbvc|tdbge|tib|tibvs|tibcc|tibne|tibcs|tibgt|tibpl|tibls|tibal|tibmi|tibhi|tiblt|tibeq|tible|tibvc|tibge|tfa|tfavs|tfacc|tfane|tfacs|tfagt|tfapl|tfals|tfaal|tfami|tfahi|tfalt|tfaeq|tfale|tfavc|tfage|mia|miavs|miacc|miane|miacs|miagt|miapl|mials|miaal|miami|miahi|mialt|miaeq|miale|miavc|miage|med|medvs|medcc|medne|medcs|medgt|medpl|medls|medal|medmi|medhi|medlt|medeq|medle|medvc|medge|mea|meavs|meacc|meane|meacs|meagt|meapl|meals|meaal|meami|meahi|mealt|meaeq|meale|meavc|meage|mfd|mfdvs|mfdcc|mfdne|mfdcs|mfdgt|mfdpl|mfdls|mfdal|mfdmi|mfdhi|mfdlt|mfdeq|mfdle|mfdvc|mfdge|mda|mdavs|mdacc|mdane|mdacs|mdagt|mdapl|mdals|mdaal|mdami|mdahi|mdalt|mdaeq|mdale|mdavc|mdage|mdb|mdbvs|mdbcc|mdbne|mdbcs|mdbgt|mdbpl|mdbls|mdbal|mdbmi|mdbhi|mdblt|mdbeq|mdble|mdbvc|mdbge|mib|mibvs|mibcc|mibne|mibcs|mibgt|mibpl|mibls|mibal|mibmi|mibhi|miblt|mibeq|mible|mibvc|mibge|mfa|mfavs|mfacc|mfane|mfacs|mfagt|mfapl|mfals|mfaal|mfami|mfahi|mfalt|mfaeq|mfale|mfavc|mfage|strb|strbvs|strbcc|strbne|strbcs|strbgt|strbpl|strbls|strbal|strbmi|strbhi|strblt|strbeq|strble|strbvc|strbge|ldrb|ldrbvs|ldrbcc|ldrbne|ldrbcs|ldrbgt|ldrbpl|ldrbls|ldrbal|ldrbmi|ldrbhi|ldrblt|ldrbeq|ldrble|ldrbvc|ldrbge|ands|andsvs|andscc|andsne|andscs|andsgt|andspl|andsls|andsal|andsmi|andshi|andslt|andseq|andsle|andsvc|andsge|eors|eorsvs|eorscc|eorsne|eorscs|eorsgt|eorspl|eorsls|eorsal|eorsmi|eorshi|eorslt|eorseq|eorsle|eorsvc|eorsge|subs|subsvs|subscc|subsne|subscs|subsgt|subspl|subsls|subsal|subsmi|subshi|subslt|subseq|subsle|subsvc|subsge|rsbs|rsbsvs|rsbscc|rsbsne|rsbscs|rsbsgt|rsbspl|rsbsls|rsbsal|rsbsmi|rsbshi|rsbslt|rsbseq|rsbsle|rsbsvc|rsbsge|adds|addsvs|addscc|addsne|addscs|addsgt|addspl|addsls|addsal|addsmi|addshi|addslt|addseq|addsle|addsvc|addsge|adcs|adcsvs|adcscc|adcsne|adcscs|adcsgt|adcspl|adcsls|adcsal|adcsmi|adcshi|adcslt|adcseq|adcsle|adcsvc|adcsge|sbcs|sbcsvs|sbcscc|sbcsne|sbcscs|sbcsgt|sbcspl|sbcsls|sbcsal|sbcsmi|sbcshi|sbcslt|sbcseq|sbcsle|sbcsvc|sbcsge|rscs|rscsvs|rscscc|rscsne|rscscs|rscsgt|rscspl|rscsls|rscsal|rscsmi|rscshi|rscslt|rscseq|rscsle|rscsvc|rscsge|tsts|tstsvs|tstscc|tstsne|tstscs|tstsgt|tstspl|tstsls|tstsal|tstsmi|tstshi|tstslt|tstseq|tstsle|tstsvc|tstsge|teqs|teqsvs|teqscc|teqsne|teqscs|teqsgt|teqspl|teqsls|teqsal|teqsmi|teqshi|teqslt|teqseq|teqsle|teqsvc|teqsge|cmps|cmpsvs|cmpscc|cmpsne|cmpscs|cmpsgt|cmpspl|cmpsls|cmpsal|cmpsmi|cmpshi|cmpslt|cmpseq|cmpsle|cmpsvc|cmpsge|cmns|cmnsvs|cmnscc|cmnsne|cmnscs|cmnsgt|cmnspl|cmnsls|cmnsal|cmnsmi|cmnshi|cmnslt|cmnseq|cmnsle|cmnsvc|cmnsge|orrs|orrsvs|orrscc|orrsne|orrscs|orrsgt|orrspl|orrsls|orrsal|orrsmi|orrshi|orrslt|orrseq|orrsle|orrsvc|orrsge|movs|movsvs|movscc|movsne|movscs|movsgt|movspl|movsls|movsal|movsmi|movshi|movslt|movseq|movsle|movsvc|movsge|bics|bicsvs|bicscc|bicsne|bicscs|bicsgt|bicspl|bicsls|bicsal|bicsmi|bicshi|bicslt|bicseq|bicsle|bicsvc|bicsge|mvns|mvnsvs|mvnscc|mvnsne|mvnscs|mvnsgt|mvnspl|mvnsls|mvnsal|mvnsmi|mvnshi|mvnslt|mvnseq|mvnsle|mvnsvc|mvnsge)\\b',
           caseInsensitive: true },
         { token: 'variable.parameter.register.assembly',
           regex: '\\b(?:r[0-9]|r1[0-5]|sl|fp|ip|sp|lr|pc|cpsr|spsr)\\b',
           caseInsensitive: true },
         { token: 'sectiontitle.assembly',
           regex: 'SECTION\\s(?:INTVEC|CODE|DATA)' },
         { token: 'memdeclare.assembly',
           regex: '[ \t]D[CS](?:8|16|32)\\b' },
         { token: 'constant.character.assembly',
           regex: '[ \t]#?0x[0-9a-fA-F]*' },
         { token: 'constant.character.assembly',
           regex: '[ \t]#?[0-9]*' },
         { token: 'label.assembly',
           regex: '^[ \t]*[a-zA-Z0-9_]*' },
         { token: 'asmcomment.assembly',
           regex: ';.*$' },
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
