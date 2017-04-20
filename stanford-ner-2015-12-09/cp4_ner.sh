#!/bin/bash
for f in ./../cp4_documents/*
	do 
		if [ ! -d  ./../cp4_annotated_documents/$(basename $f) ]
		then 
			mkdir ./../cp4_annotated_documents/$(basename $f)
		fi
		for g in $f/*
			do 
			java -mx600m -cp "*:lib/*" edu.stanford.nlp.ie.crf.CRFClassifier -loadClassifier classifiers/english.all.3class.distsim.crf.ser.gz -outputFormat inlineXML -textFile $g > ./../cp4_annotated_documents/$(basename $f)/$(basename $g)
			done
	done